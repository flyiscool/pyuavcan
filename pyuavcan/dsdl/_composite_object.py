#
# Copyright (c) 2019 UAVCAN Development Team
# This software is distributed under the terms of the MIT License.
# Author: Pavel Kirienko <pavel.kirienko@zubax.com>
#

from __future__ import annotations
import abc
import gzip
import typing
import pickle
import base64
import logging
import importlib

import pydsdl

from . import _serialized_representation


_logger = logging.getLogger(__name__)


class CompositeObject(abc.ABC):  # Members are surrounded with underscores to avoid collisions with DSDL attributes.
    """
    This is the base class for all Python classes generated from DSDL definitions.
    It does not have any public members.
    """

    # Type definition as provided by PyDSDL.
    _MODEL_: pydsdl.CompositeType

    # Defined in generated classes.
    _MAX_SERIALIZED_REPRESENTATION_SIZE_BYTES_: int

    @abc.abstractmethod
    def _serialize_aligned_(self, _ser_: _serialized_representation.Serializer) -> None:
        """
        Auto-generated serialization method.
        Appends the serialized representation of its object to the supplied Serializer instance.
        The current bit offset of the Serializer instance MUST be byte-aligned.
        This is not a part of the API.
        """
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def _deserialize_aligned_(_des_: _serialized_representation.Deserializer) -> CompositeObject:
        """
        Auto-generated deserialization method. Consumes (some) data from the supplied Deserializer instance.
        Raises a Deserializer.FormatError if the supplied serialized representation is invalid.
        Always returns a valid object unless an exception is raised.
        The current bit offset of the Deserializer instance MUST be byte-aligned.
        This is not a part of the API.
        """
        raise NotImplementedError

    @staticmethod
    def _restore_constant_(encoded_string: str) -> object:
        """Recovers a pickled gzipped constant object from base85 string representation."""
        out = pickle.loads(gzip.decompress(base64.b85decode(encoded_string)))
        assert isinstance(out, object)
        return out

    # These typing hints are provided here for use in the generated classes. They are obviously not part of the API.
    _SerializerTypeVar_ = typing.TypeVar('_SerializerTypeVar_', bound=_serialized_representation.Serializer)
    _DeserializerTypeVar_ = typing.TypeVar('_DeserializerTypeVar_', bound=_serialized_representation.Deserializer)


class ServiceObject(CompositeObject):
    """
    This is the base class for all Python classes generated from DSDL service type definitions.
    Observe that it inherits from the composite object class, just like the nested types Request and Response.
    """
    #: Nested request type. Inherits from :class:`CompositeObject`.
    #: The base class provides a stub which is overridden in generated classes.
    Request: typing.Type[CompositeObject]

    #: Nested response type. Inherits from :class:`CompositeObject`.
    #: The base class provides a stub which is overridden in generated classes.
    Response: typing.Type[CompositeObject]

    _MAX_SERIALIZED_REPRESENTATION_SIZE_BYTES_ = 0

    def _serialize_aligned_(self, _ser_: _serialized_representation.Serializer) -> None:
        raise TypeError(f'Service type {type(self).__name__} cannot be serialized')

    @staticmethod
    def _deserialize_aligned_(_des_: _serialized_representation.Deserializer) -> CompositeObject:
        raise TypeError('Service types cannot be deserialized')


class FixedPortObject(abc.ABC):
    """
    This is the base class for all Python classes generated from DSDL types that have a fixed port identifier.
    """
    _FIXED_PORT_ID_: int


class FixedPortCompositeObject(CompositeObject, FixedPortObject):
    @abc.abstractmethod
    def _serialize_aligned_(self, _ser_: _serialized_representation.Serializer) -> None:
        raise NotImplementedError

    @staticmethod
    @abc.abstractmethod
    def _deserialize_aligned_(_des_: _serialized_representation.Deserializer) -> CompositeObject:
        raise NotImplementedError


class FixedPortServiceObject(ServiceObject, FixedPortObject):
    pass


CompositeObjectTypeVar = typing.TypeVar('CompositeObjectTypeVar', bound=CompositeObject)


# noinspection PyProtectedMember
def serialize(obj: CompositeObject) -> typing.Iterable[memoryview]:
    """
    Constructs a serialized representation of the provided top-level object.
    The resulting serialized representation is padded to one byte in accordance with the UAVCAN specification.
    The constructed serialized representation is returned as a sequence of byte-aligned fragments which must be
    concatenated in order to obtain the final representation.
    The objective of this model is to avoid copying data into a temporary buffer when possible.
    Each yielded fragment is of type :class:`memoryview` pointing to raw unsigned bytes.
    It is guaranteed that at least one fragment is always returned (which may be empty).
    """
    # TODO: update the Serializer class to emit an iterable of fragments.
    ser = _serialized_representation.Serializer.new(obj._MAX_SERIALIZED_REPRESENTATION_SIZE_BYTES_)
    obj._serialize_aligned_(ser)
    yield ser.buffer.data


# noinspection PyProtectedMember
def deserialize(dtype: typing.Type[CompositeObjectTypeVar],
                fragmented_serialized_representation: typing.Sequence[memoryview]) \
        -> typing.Optional[CompositeObjectTypeVar]:
    """
    Constructs an instance of the supplied DSDL-generated data type from its serialized representation.
    Returns None if the provided serialized representation is invalid.

    This function will never raise an exception for invalid input data; the only possible outcome of an invalid data
    being supplied is None at the output. A raised exception can only indicate an error in the deserialization logic.

    .. important:: The constructed object may contain arrays referencing the memory allocated for the serialized
        representation. Therefore, in order to avoid unintended data corruption, the caller should destroy all
        references to the serialized representation immediately after the invocation.

    .. important:: The supplied fragments of the serialized representation should be writeable.
        If they are not, some of the array-typed fields of the constructed object may be read-only.
    """
    # TODO: update the Deserializer class to support fragmented input.
    # join() on one element will create a copy, so that is very expensive.
    if len(fragmented_serialized_representation) == 1:  # Optimized hot path; no memory reallocation whatsoever
        contiguous: typing.Union[bytearray, memoryview] = fragmented_serialized_representation[0]
    else:
        contiguous = bytearray().join(fragmented_serialized_representation)
    deserializer = _serialized_representation.Deserializer.new(contiguous)
    try:
        return dtype._deserialize_aligned_(deserializer)  # type: ignore
    except _serialized_representation.Deserializer.FormatError:
        # Use explicit level check to avoid unnecessary load in production.
        # This is necessary because we perform complex data transformations before invoking the logger.
        if _logger.isEnabledFor(logging.INFO):  # pragma: no branch
            _logger.info('Invalid serialized representation of %s: %s', get_model(dtype), deserializer, exc_info=True)
        return None


def get_model(class_or_instance: typing.Union[typing.Type[CompositeObject], CompositeObject]) -> pydsdl.CompositeType:
    """
    Obtains a PyDSDL model of the supplied DSDL-generated class or its instance.
    This is the inverse of :func:`get_class`.
    """
    # noinspection PyProtectedMember
    out = class_or_instance._MODEL_
    assert isinstance(out, pydsdl.CompositeType)
    return out


def get_class(model: pydsdl.CompositeType) -> typing.Type[CompositeObject]:
    """
    Returns a generated native class implementing the specified DSDL type represented by its PyDSDL model object.
    This is the inverse of :func:`get_model`.

    :raises: :class:`ImportError` if the generated package or subpackage cannot be found;
        :class:`AttributeError` if the package is found but it does not contain the requested type.
    """
    if model.parent_service is not None:    # uavcan.node.GetInfo.Request --> uavcan.node.GetInfo then Request
        out = get_class(model.parent_service)
        assert issubclass(out, ServiceObject)
        out = getattr(out, model.short_name)
    else:
        mod = None
        for comp in model.name_components[:-1]:
            name = (mod.__name__ + '.' + comp) if mod else comp  # type: ignore
            try:
                mod = importlib.import_module(name)
            except ImportError:                         # We seem to have hit a reserved word; try with an underscore.
                mod = importlib.import_module(name + '_')
        ref = f'{model.short_name}_{model.version.major}_{model.version.minor}'
        out = getattr(mod, ref)
        assert get_model(out) == model

    assert issubclass(out, CompositeObject)
    return out


def get_max_serialized_representation_size_bytes(class_or_instance: typing.Union[typing.Type[CompositeObject],
                                                                                 CompositeObject]) -> int:
    # noinspection PyProtectedMember
    return int(class_or_instance._MAX_SERIALIZED_REPRESENTATION_SIZE_BYTES_)


def get_fixed_port_id(class_or_instance: typing.Union[typing.Type[FixedPortObject],
                                                      FixedPortObject]) -> typing.Optional[int]:
    """
    Returns None if the supplied type has no fixed port-ID.
    """
    try:
        # noinspection PyProtectedMember
        out = int(class_or_instance._FIXED_PORT_ID_)
    except TypeError:
        return None
    else:
        if (isinstance(class_or_instance, type) and issubclass(class_or_instance, CompositeObject)) or \
                isinstance(class_or_instance, CompositeObject):  # pragma: no branch
            assert out == get_model(class_or_instance).fixed_port_id
        return out


def get_attribute(obj: typing.Union[CompositeObject, typing.Type[CompositeObject]],
                  name: str) -> typing.Any:
    """
    DSDL type attributes whose names can't be represented in Python (such as ``def`` or ``type``)
    are suffixed with an underscore.
    This function allows the caller to read arbitrary attributes referring to them by their original
    DSDL names, e.g., ``def`` instead of ``def_``.

    This function behaves like :func:`getattr` if the attribute does not exist.
    """
    try:
        return getattr(obj, name)
    except AttributeError:
        return getattr(obj, name + '_')


def set_attribute(obj: CompositeObject, name: str, value: typing.Any) -> None:
    """
    DSDL type attributes whose names can't be represented in Python (such as ``def`` or ``type``)
    are suffixed with an underscore.
    This function allows the caller to assign arbitrary attributes referring to them by their original DSDL names,
    e.g., ``def`` instead of ``def_``.

    If the attribute does not exist, raises :class:`AttributeError`.
    """
    suffixed = name + '_'
    # We can't call setattr() without asking first because if it doesn't exist it will be created,
    # which would be disastrous.
    if hasattr(obj, name):
        setattr(obj, name, value)
    elif hasattr(obj, suffixed):
        setattr(obj, suffixed, value)
    else:
        raise AttributeError(name)
