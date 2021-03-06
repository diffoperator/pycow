import copy

primitive_types = (int, bool, float, long, complex)
sequence_types = (str, unicode, list, tuple, bytearray, buffer, xrange)

class Proxy(object):
    """
    The proxy is a transparent wrapper that intercepts all access to the
    underlying object. When first created, it creates a shallow copy
    of the underlying object and behaves like a shadow reference. When
    any attribute of the underlying object is modified, the Proxy either
    creates a complete deep copy (it deep copies the entire object it was
    tracking) or creates a partial deep copy (it deep copies only the
    attribute that was touched). This behavior is triggered by an appropriate
    flag.

    Example:
    >>> class Point:
    ...     x = None
    ...     y = None
    ...     def __init__(self, x, y):
    ...         self.x = x
    ...         self.y = y

    >>> class TwoPoints:
    ...     a = None
    ...     b = None
    ...     def __init__(self, a, b):
    ...         self.a = a
    ...         self.b = b

    >>> a = Point(1,2)
    >>> b = Point(3,4)
    >>> c = TwoPoints(a,b)
    >>> d = Proxy(c)
    """
    __slots__ = ["_obj", "__weakref__", "__slots__", "_is_copied",
                 "_enable_partial_copy", "_attr_map"]
    
    _is_copied = False
    _attr_map = {}
    
    def __init__(self, obj, _partial_copy=False):
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_enable_partial_copy", _partial_copy)
    
    def __getattribute__(self, name):
        """
        In order to fetch the attribute of the underlying object,
        the proxy redirects the call to the reference of the
        underlying object, _obj.
        """
        slots = object.__getattribute__(self, "__slots__")
        attr_map = object.__getattribute__(self, "_attr_map")
        if name not in slots:
            if not self._is_copied:
                if name in attr_map:
                    if not self._enable_partial_copy and attr_map[name]._is_copied:
                        # If we have not enabled partial copying then deep copy the
                        # reference to the main object
                        self._obj = copy.deepcopy(self._obj)
                        self._is_copied = True

                        # Replace all the attributes in the deep copied object with
                        # those in the attribute map
                        for attr_map_entry in attr_map:
                            if not attr_map[attr_map_entry]._is_copied:
                                attr_map[attr_map_entry]._obj = copy.deepcopy(attr_map[attr_map_entry]._obj)
                                attr_map[attr_map_entry]._is_copied = True
                            setattr(self._obj, attr_map_entry, attr_map[attr_map_entry]._obj)
                        
                        return getattr(object.__getattribute__(self, "_obj"), name)
                    else:
                        return attr_map[name]

                attr = getattr(object.__getattribute__(self, "_obj"), name)

                if isinstance(attr, primitive_types):
                    return attr

                proxy_attr = Proxy(attr)
                attr_map[name] = proxy_attr

                object.__setattr__(self, "_attr_map", attr_map)

                return proxy_attr
            else:
                return getattr(object.__getattribute__(self, "_obj"), name)
        elif name == "__class__":
            return getattr(object.__getattribute__(self, "_obj"), "__class__")
        else:
            return object.__getattribute__(self, name)

    def __delattr__(self, name):
        slots = object.__getattribute__(self, "__slots__")
        if name not in slots:
            delattr(object.__getattribute__(self, "_obj"), name)
        else:
            raise Exception("Modification of proxy objects can lead to unexpected behavior")

    def __setattr__(self, name, value):
        slots = object.__getattribute__(self, "__slots__")
        attr_map = object.__getattribute__(self, "_attr_map")
        if name not in slots:
            # If we are not partially copying, copy everything
            if not self._is_copied and not self._enable_partial_copy:
                self._obj = copy.deepcopy(self._obj)
                self._is_copied = True
            
            # If partial copying is enabled, store the new value in the attribute map
            if self._enable_partial_copy:
                self._attr_map[name] = value
                return

            setattr(object.__getattribute__(self, "_obj"), name, value)
            if name in attr_map:
                attr_map[name] = value
            object.__setattr__(self, "_attr_map", attr_map)
        else:
            object.__setattr__(self, name, value)

    _special_names = [
        '__abs__', '__add__', '__and__', '__call__', '__cmp__', '__coerce__', 
        '__contains__', '__delitem__', '__delslice__', '__div__', '__divmod__', 
        '__eq__', '__float__', '__floordiv__', '__ge__', '__getitem__', 
        '__getslice__', '__gt__', '__hash__', '__hex__', '__iadd__', '__iand__',
        '__idiv__', '__idivmod__', '__ifloordiv__', '__ilshift__', '__imod__', 
        '__imul__', '__int__', '__invert__', '__ior__', '__ipow__', '__irshift__', 
        '__isub__', '__iter__', '__itruediv__', '__ixor__', '__le__', '__len__', 
        '__long__', '__lshift__', '__lt__', '__mod__', '__mul__', '__ne__', 
        '__neg__', '__nonzero__', '__oct__', '__or__', '__pos__', '__pow__', 
        '__radd__', '__rand__', '__rdiv__', '__rdivmod__', '__reduce__', '__reduce_ex__', 
        '__repr__', '__reversed__', '__rfloorfiv__', '__rlshift__', '__rmod__', 
        '__rmul__', '__ror__', '__rpow__', '__rrshift__', '__rshift__', '__rsub__', 
        '__rtruediv__', '__rxor__', '__setitem__', '__setslice__', '__str__',
        '__sub__', '__truediv__', '__xor__', 'next',
    ]
    
    @classmethod
    def _create_class_proxy(cls, theclass):
        """creates a proxy for the given class"""
        
        def make_method(name):
            def method(self, *args, **kw):
                if name in cls._special_names and args is not ():
                    args = map(lambda x: x._obj if isinstance(x, Proxy) else x, args)
                return getattr(object.__getattribute__(self, "_obj"), name)(*args, **kw)
            return method
        
        namespace = {}
        for name in cls._special_names:
            if hasattr(theclass, name):
                namespace[name] = make_method(name)
        return type("%s(%s)" % (cls.__name__, theclass.__name__), (cls,), namespace)
    
    def __new__(cls, obj, *args, **kwargs):
        """
        creates an proxy instance referencing `obj`. (obj, *args, **kwargs) are
        passed to this class' __init__, so deriving classes can define an 
        __init__ method of their own.
        note: _class_proxy_cache is unique per deriving class (each deriving
        class must hold its own cache)
        """
        try:
            cache = cls.__dict__["_class_proxy_cache"]
        except KeyError:
            cls._class_proxy_cache = cache = {}
        try:
            theclass = cache[obj.__class__]
        except KeyError:
            cache[obj.__class__] = theclass = cls._create_class_proxy(obj.__class__)
        ins = object.__new__(theclass)
        theclass.__init__(ins, obj, *args, **kwargs)
        return ins
