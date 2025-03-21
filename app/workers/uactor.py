"""uActor module."""
"""
uActor: Process Actor Model
===========================

See `README.md`_ provided in source distributions or available
at the `project repository`_.

.. _README.md: https://gitlab.com/ergoithz/uactor/-/blob/master/README.md
.. _project repository: https://gitlab.com/ergoithz/uactor

License
-------

Copyright (c) 2020, Felipe A Hernandez.

MIT License (see `LICENSE`_).

.. _LICENSE: https://gitlab.com/ergoithz/uactor/-/blob/master/LICENSE

"""

import weakref
import typing
import types
import multiprocessing.managers
import multiprocessing
import functools
import collections
__author__ = 'Felipe A Hernandez'
__email__ = 'ergoithz@gmail.com'
__license__ = 'MIT'
__version__ = '0.1.1'
__all__ = (
    'DEFAULT_SERIALIZER',
    'UActorException',
    'ProxyError',
    'AuthkeyError',
    'BaseProxy',
    'ActorManager',
    'ActorProxy',
    'Actor',
    'proxy',
    'typeid',
)


DEFAULT_SERIALIZER = 'pickle'
"""
Default :mod:`multiprocessing.managers` serializer name for :mod:`uactor`.

.. versionadded:: 0.1.1

"""

Token = multiprocessing.managers.Token
BaseManager = multiprocessing.managers.BaseManager

TActor = typing.TypeVar('TActor', bound='Actor')
TActorProxy = typing.TypeVar('TActorProxy', bound='ActorProxy')
TActorManager = typing.TypeVar('TActorManager', bound='ActorManager')
AddressType = typing.Union[typing.Tuple[str, int], str, bytes, int]

autoproxy_classes = weakref.WeakValueDictionary()
process_managers = weakref.WeakValueDictionary()
connection_managers = weakref.WeakValueDictionary()


def bootstrap(manager: 'ActorManager',
              cls: typing.Type['Actor'],
              args: typing.Iterable[typing.Any],
              kwargs: typing.Dict[str, typing.Any],
              ) -> None:
    """
    Actor process initialization function.

    .. versionadded:: 0.1.0

    """
    process = multiprocessing.current_process()
    process._uactor_manager = manager
    process._uactor_class = cls
    process._uactor_owner = cls(*args, **kwargs)


def current_actor(actor: typing.Optional[TActor] = None) -> TActor:
    """Get current process actor object, used as proxy constructor."""
    current = multiprocessing.current_process()._uactor_owner
    if actor not in (None, current):
        # we must not use an invalid proxy on a foreign actor
        raise ProxyError(
            'Proxy \'actor\' cannot be used with foreign actor references',
        )
    return current


def proxy_method(actor_class: typing.Type['Actor'],
                 name: str) -> typing.Union[callable, property]:
    """Create proxy method/property from class and attribute name."""
    wrapped = getattr(actor_class, name, None)
    if callable(wrapped):
        def wrapper(proxy, *args, **kwargs):
            return proxy._callmethod(name, args, kwargs)
        return functools.update_wrapper(wrapper, wrapped), ()

    def fget(proxy):
        return proxy._callmethod('__getattribute__', (name,))

    def fset(proxy, value):
        return proxy._callmethod('__setattr__', (name, value))

    return property(fget, fset), ('__getattribute__', '__setattr__')


def proxy(value: typing.Any,
          typeid: str = 'auto',
          serializer: str = DEFAULT_SERIALIZER,
          ) -> 'BaseProxy':
    """
    Create serialized proxy from given value and typeid (defaults to `auto`).

    This function can be only used from inside the actor process.

    .. versionadded:: 0.1.0

    """
    process = multiprocessing.current_process()
    try:
        server = process._manager_server
        manager = process._uactor_manager
        proxytype = server.registry[typeid][-1]
    except AttributeError:
        raise ProxyError(
            'Proxies can only be created under actor processes',
        ) from None
    except KeyError:
        raise ProxyError(
            f'No proxy is registered with typeid {typeid!r}',
        ) from None
    # FIXME: if someday the connection became required, we would need to
    #        subclass multiprocessing.managers.Server to expose it as a
    #        thread local
    ident, exposed = server.create(None, typeid, value)
    token = multiprocessing.managers.Token(typeid, server.address, ident)
    options = {'manager': manager, 'exposed': exposed, 'incref': False}
    return proxytype(token, serializer, **options)


def typeid(proxy: 'BaseProxy') -> str:
    """
    Get typeid from given proxy object.

    .. versionadded:: 0.1.0

    """
    try:
        return proxy._token.typeid
    except AttributeError:
        exc_type, exc_message = (
            (ProxyError, 'Cannot get typeid, proxy token not available')
            if isinstance(proxy, BaseProxy) else
            (ValueError, f'Cannot get typeid, {proxy!r} is not a proxy')
        )
        raise exc_type(exc_message) from None


def rebuild_manager(manager_class: typing.Type[TActorManager],
                    address: AddressType,
                    authkey: typing.Optional[bytes] = None,
                    serializer: str = DEFAULT_SERIALIZER,
                    ) -> TActorManager:
    """
    Rebuild manager from basic params and cache.

    .. versionadded:: 0.1.1

    """
    key = manager_class, address
    manager = connection_managers.get(key)
    matching = (
        manager
        and authkey in (None, manager._authkey)
        and serializer == manager._serializer
    )
    if not matching:
        manager = manager_class(
            address,
            authkey,
            serializer,
            parent=process_managers.get(key),
        )
        manager.connect()
    return manager


def rebuild_proxy(manager_class: typing.Type['ActorManager'],
                  builder: typing.Callable[..., 'BaseProxy'],
                  proxytype: typing.Type['BaseProxy'],
                  token: Token,
                  serializer: str,
                  *args,
                  ) -> 'BaseProxy':
    """
    Rebuild proxy from serialization data.

    .. versionadded:: 0.1.1

    """
    manager = rebuild_manager(manager_class, token.address, None, serializer)
    params = {'manager': manager}
    token.address = manager.address  # rewrite token address with managed one

    if not isinstance(proxytype, type):
        params['proxytype'] = proxytype
        proxytype = rebuild_autoproxy

    # FIXME: private-implementation-specific code
    args[-1].update(params)
    return builder(proxytype, token, serializer, *args)


def rebuild_autoproxy(token: 'Token',
                      serializer: str,
                      *args,
                      proxytype: typing.Optional[type] = None,
                      **kwd,
                      ) -> 'BaseProxy':
    """
    Create and convert autoproxy to uactor proxy.

    The wrapping mechanism is intended as a workaround for multiprocessing
    bugs causing the loss of authkey and manager on nested proxies.

    .. versionadded:: 0.1.1

    """
    proxy = proxytype(token, serializer, *args, **kwd)
    proxytype = type(proxy)
    if proxytype not in autoproxy_classes:
        autoproxy_classes[proxytype] = type(
            proxytype.__name__,
            (BaseProxy, proxytype),
            {'_isauto': getattr(proxy, '_isauto', False)},
        )
    return autoproxy_classes[proxytype](token, serializer, *args, **kwd)


def extract_proxies(base: typing.Type[BaseManager],
                    ) -> typing.Dict[str, callable]:
    """
    Create an updated copy from the registry of given manager.

    .. versionadded:: 0.1.1

    """
    proxies = {}
    context = globals()
    manager = type('Workbench', (base,), {})
    manager.register('auto', create_method=False)
    for typeid, params in manager._registry.items():
        # FIXME: private-implementation-specific code
        proxytype = params[3]
        if isinstance(proxytype, type):
            # BaseProxy subclass
            proxytype = type(f'Proxy[{typeid}]', (BaseProxy, proxytype), {})
            context[proxytype.__name__] = proxytype
        else:
            # AutoProxy factory
            proxytype = functools.update_wrapper(
                functools.partial(rebuild_autoproxy, proxytype=proxytype),
                proxytype,
            )
        proxies[typeid] = proxytype
    return proxies


class UActorException(Exception):
    """
    Base exception for uactor module.

    .. versionadded:: 0.1.0

    """


class ProxyError(UActorException):
    """
    Exception for errors on proxy logic.

    .. versionadded:: 0.1.0

    """


class AuthkeyError(ProxyError):
    """
    Exception raised when connecting to proxy with invalid authkey.

    .. versionadded:: 0.1.1

    """


class CollisionDict(collections.UserDict):
    """
    Dictionary raising an exception when overwriting existing keys.

    .. versionadded:: 0.1.1

    """

    def __init__(self,
                 data: typing.MutableMapping,
                 exc_type: typing.Type['UActorException'],
                 exc_args: typing.Sequence[typing.Any]):
        """Initialize."""
        self.exc_type = exc_type
        self.exc_args = exc_args
        super().__init__(data)

    def __setitem__(self, key: typing.Hashable, value: typing.Any):
        """Set proxy data for an id."""
        if self.get(key) not in (None, value):
            raise self.exc_type(*self.exc_args)
        super().__setitem__(key, value)


class BaseProxy(multiprocessing.managers.BaseProxy):
    """
    Base Proxy class.

    This class implements a few workarounds around bugs found in
    :class:`multiprocessing.managers.BaseProxy` by preventing
    :attr:`BaseProxy._manager` from getting lost on both unserialization
    and process forking by recreating it on demand.

    .. versionadded:: 0.1.0

    """

    @property
    def _manager(self) -> 'ActorManager':
        """Get set manager."""
        return self._manager_instance

    @_manager.setter
    def _manager(self, manager: typing.Optional['ActorManager']):
        """Set manager or create a new one when trying to unset."""
        self._manager_instance = manager or rebuild_manager(
            type(self._manager_instance),
            self._token.address,
            self._authkey,
            self._serializer,
        )

    def _callmethod(self, *args, **kwargs):
        """Call method of proxied object."""
        result = super()._callmethod(*args, **kwargs)
        # FIXME: find a more elegant way of doing this
        if isinstance(result, BaseProxy) and result._manager.process:
            result._manager = None
        return result

    def __reduce__(self) -> tuple:
        """Implement the pickle reduce protocol."""
        # FIXME: private-implementation-specific code (python bug workaround)
        manager_class = type(self._manager)
        builder, args, *state = super().__reduce__()
        return (rebuild_proxy, (manager_class, builder, *args), *state)


class ActorManager(BaseManager):
    """
    Multiprocessing manager for uactor.

    .. versionadded:: 0.1.0

    """

    @classmethod
    def _Server(cls, *args, **kwargs):
        """Return server object patched with proxy collision checks."""
        # FIXME: private-implementation-specific code (python bug workaround)
        server = super()._Server(*args, **kwargs)
        server.id_to_obj = CollisionDict(
            server.id_to_obj,
            ProxyError,
            ('Two different proxies cannot point to the same object',),
        )
        return server

    @classmethod
    def typeids(cls) -> typing.Tuple[str, ...]:
        """Get tuple of typeid of all registered proxies."""
        return tuple(cls._registry)

    @property
    def process(self) -> typing.Optional[multiprocessing.Process]:
        """Get remote actor process if owned by this manager."""
        return getattr(self, '_process', None)

    def __init__(self,
                 address: typing.Optional['AddressType'] = None,
                 authkey: typing.Optional[bytes] = None,
                 serializer: str = DEFAULT_SERIALIZER,
                 *args,
                 parent: typing.Optional['ActorManager'] = None,
                 **kwargs):
        """Initialize manager."""
        self.parent = parent
        authkey = authkey or (parent._authkey if parent else None)
        super().__init__(address, authkey, serializer, *args, **kwargs)

    def start(self, *args, **kwargs):
        """Start manager process."""
        super().start(*args, **kwargs)
        process_managers[type(self), self.address] = self

    def connect(self):
        """
        Connect to manager process.

        :raises AuthkeyError: on actor process authkey rejection.
        """
        try:
            super().connect()
            connection_managers[type(self), self.address] = self
        except multiprocessing.context.AuthenticationError as e:
            raise AuthkeyError(
                'Actor process rejected provided authkey',
            ) from e


class ActorProxy(BaseProxy):
    """
    Actor proxy base class.

    Actors will inherit from this class to create custom implementations based
    on their declared configuration and interface.

    .. versionadded:: 0.1.0

    """

    @property
    def connection_address(self) -> AddressType:
        """
        Get connection address to :class:`Actor` process.

        .. versionadded:: 0.1.1

        """
        return self._token.address

    def __enter__(self, *args, **kwargs):
        """Call :meth:`Actor.__enter__` method."""
        return self._callmethod('__enter__', args, kwargs)

    def __exit__(self, *args, **kwargs):
        """
        Call :meth:`Actor.__exit__` method.

        When this proxy is the direct result from instancing
        the :class:`Actor` class, calling this method will
        also result on :meth:`Actor.shutdown` being called,
        finishing the actor process (like when calling
        :meth:`ActorProxy.shutdown`).

        """
        try:
            return self._callmethod('__exit__', args, kwargs)
        finally:
            if self._manager.process:
                self._callmethod('shutdown')
                self._manager.shutdown()

    def shutdown(self):
        """
        Call :meth:`Actor.shutdown` method.

        When the current process is responsible of initializing
        the actor, calling this method will also finish the actor
        process.

        """
        try:
            return self._callmethod('shutdown')
        finally:
            manager = self._manager.parent or self._manager
            if manager.process:
                manager.shutdown()


class Actor:
    """
    Actor base class for actor implementations to inherit from.

    An actor represents a processing unit. During instantiation,
    a new actor process is be started, and the corresponding
    proxy is returned.

    Actors also implement the context manager interface, and you can override
    both :meth:`Actor.__enter__` and :meth:`Actor.__exit__` to implement your
    own logic, but keep in mind they're both specially handled and calling
    :meth:`ActorProxy.__exit__` will also terminate the process (just
    like calling :meth:`ActorProxy.shutdown`).

    .. versionadded:: 0.1.0

    """

    manager_class = ActorManager
    """
    :class:`ActorManager` subclass used to initialize the actor process.

    Whatever is defined here, will be subclassed during actor class
    initialization to apply the declared actor configuration.
    """

    proxy_class = ActorProxy
    """
    :class:`ActorProxy` subclass used to initialize the actor proxy.

    Whatever is defined here, will be subclassed during actor class
    initialization to apply the declared actor configuration.
    """

    _options_: typing.Mapping[str, typing.Any] = {}
    """
    Option :class:`dict` will be passed to :class:`Actor.manager_class`.

    This options mapping is passed to :class:`Actor.manager_class` during
    :class:`Actor` instantiation.
    """

    _exposed_: typing.Optional[typing.Tuple[str]] = (
        '__enter__',
        '__exit__',
        'shutdown',
    )
    """
    :class:`tuple` containing then list of method/properties will be exposed.

    Class inheritance will be honored when using this attribute.
    """

    _proxies_: typing.Mapping[str, typing.Type[BaseProxy]] = extract_proxies(
        multiprocessing.managers.SyncManager,
    )
    """
    Proxy :class:`dict` of typeid keys and :class:`BaseProxy` values.

    Proxies defined here will be registered at :class:`Actor.manager_class`
    and will be made available from within the actor process.
    """

    _method_to_typeid_: typing.Mapping[str, str] = {
        '__enter__': 'actor',
    }
    """
    Configuration :class:`dict` of method name keys and typeid values.

    Including a method with an typeid here will result on the corresponding
    proxy to be returned when called from an :class:`ActorProxy` instance.
    """

    def __init_subclass__(cls):
        """
        Initialize actor class.

        This method is what takes our declarative actor-based interface and
        dynamically setup the components required by our usage of
        :mod:`multiprocessing.manager` functionality.

        .. versionchanged:: 0.1.1
           Replaces previous metaclass implementation.

        """
        super().__init_subclass__()
        base_vars = tuple(map(vars, reversed(cls.mro())))
        proxies = {
            typeid: proxy
            for dct in base_vars
            for typeid, proxy in (dct.get('_proxies_') or {}).items()
        }
        exposed = [
            name
            for dct in base_vars
            for exposed in (
                (
                    (
                        key
                        for key, value in dct.items()
                        if not key.startswith('_') and callable(value)
                    )
                    if dct.get('_exposed_') is None else
                    dct['_exposed_']
                ),
                (
                    dct.get('_method_to_typeid_') or ()
                ),
            )
            for name in exposed
        ]
        method_to_typeid = {
            method: typeid
            for dct in base_vars
            if dct.get('_method_to_typeid_')
            for method, typeid in dct['_method_to_typeid_'].items()
        }
        properties = [
            (name, *proxy_method(cls, name))
            for name in exposed
        ]
        exposed.extend(
            requirement
            for name, func, requirements in properties
            for requirement in requirements
        )

        invalid = set(proxies) & {'actor'}
        if invalid:
            raise TypeError(f'typeid {next(iter(invalid))!r} is reserved')
        undefined = set(method_to_typeid.values()) - {None, 'actor', *proxies}
        if undefined:
            raise TypeError(f'typeid {next(iter(undefined))!r} is not defined')

        cls.manager_class = type(
            f'{cls.__qualname__}.manager_class',
            (cls.manager_class,),
            {'__module__': cls.__module__},
        )
        cls.proxy_class = type(
            f'{cls.__qualname__}.proxy_class',
            (cls.proxy_class,),
            {
                '__module__': cls.__module__,
                '_exposed_': tuple(exposed),
                '_method_to_typeid_': {
                    method: typeid
                    for method, typeid in method_to_typeid.items()
                    if typeid is not None
                },
                **{
                    name: func
                    for name, func, requirement in properties
                    if not hasattr(cls.proxy_class, name)
                },
            },
        )
        cls.manager_class.register(
            typeid='actor',
            callable=current_actor,
            proxytype=cls.proxy_class,
            create_method=True,
        )
        for typeid, proxy in proxies.items():
            cls.manager_class.register(
                typeid=typeid,
                proxytype=proxy,
                create_method=False,
            )

    def __new__(cls, *args, **kwargs):
        """Start actor process, initialize actor and return its proxy."""
        process = multiprocessing.current_process()
        initializing = (
            getattr(process, '_uactor_class', None) is cls
            and getattr(process, '_uactor_owner', None) is None
        )
        if initializing:
            self = super().__new__(cls)
            process._uactor_owner = self  # prevent recursion on __init__
            return self
        manager = cls.manager_class(**cls._options_)
        manager.start(bootstrap, (manager, cls, args, kwargs))
        return manager.actor()

    def __init__(self):
        """
        Initialize actor.

        This method will be called once when the actor process starts.
        """
        super().__init__()

    def __enter__(self: TActor) -> TActor:
        """Enter context, return actor proxy."""
        return self

    def __exit__(self, exc_type: typing.Type[Exception], exc_val: Exception,
                 exc_tb: types.TracebackType) -> typing.Optional[bool]:
        """
        Leave context.

        Method :meth:`uactor.Actor.shutdown` will be called after
        this one when the context manager interface is used on the owner
        process.

        """

    def shutdown(self):
        """
        Perform shutdown work before the process dies (stub).

        This method will be called by explicit
        :meth:`ActorProxy.shutdown` calls, even if no real
        process shutdown is involved (ie. with remote proxy connections),
        enabling implementing remote shutdown logic here
        (ie. breaking a mainloop).

        This method will be also called after :meth:`Actor.__exit__`
        when the owner process uses the :class:`ActorProxy` context
        manager interface.

        """

    @classmethod
    def connect(cls: typing.Type[TActorProxy],
                address: AddressType,
                authkey: bytes,
                serializer: str = DEFAULT_SERIALIZER,
                capture: typing.Sequence[AddressType] = (),
                ) -> TActorProxy:
        """
        Get actor proxy instance connected to address.

        :param address: actor process connection address
        :param authkey: authentication secret key
        :param serializer: serializer name
        :param capture: iterable of additional addresses will be handled
                        with this connection.

        .. versionadded:: 0.1.1

        """
        manager_class = cls.manager_class
        manager = rebuild_manager(manager_class, address, authkey, serializer)

        # TODO: do this in a better place
        connection_managers.update(
            ((manager_class, address), manager)
            for address in capture
        )

        return manager.actor()
