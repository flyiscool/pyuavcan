#
# Copyright (c) 2019 UAVCAN Development Team
# This software is distributed under the terms of the MIT License.
# Author: Pavel Kirienko <pavel.kirienko@zubax.com>
#

import abc
import typing
import logging
import dataclasses
import pyuavcan.transport


_logger = logging.getLogger(__name__)


@dataclasses.dataclass
class RedundantSessionStatistics(pyuavcan.transport.SessionStatistics):
    """
    Aggregate statistics for all inferior sessions in a redundant group.
    This is an atomic immutable sample; it is not updated after construction.
    """
    #: The ordering is guaranteed to match that of :attr:`RedundantSession.inferiors`.
    inferiors: typing.List[pyuavcan.transport.SessionStatistics] = dataclasses.field(default_factory=list)


class RedundantSession(abc.ABC):
    """
    The base for all redundant session instances.

    A redundant session may be constructed even if the redundant transport itself has no inferiors.
    When a new inferior transport is attached/detached to/from the redundant group,
    dependent session instances are automatically reconfigured, transparently to the user.

    The higher layers of the protocol stack are therefore shielded from any changes made to the stack
    below the redundant transport instance; existing sessions and other instances are never invalidated.
    This guarantee allows one to construct applications whose underlying transport configuration
    can be changed at runtime.
    """

    @property
    @abc.abstractmethod
    def specifier(self) -> pyuavcan.transport.SessionSpecifier:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def payload_metadata(self) -> pyuavcan.transport.PayloadMetadata:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def inferiors(self) -> typing.Sequence[pyuavcan.transport.Session]:
        """
        Read-only access to the list of inferiors.
        The ordering is guaranteed to match that of :attr:`RedundantTransport.inferiors`.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def close(self) -> None:
        """
        Closes and detaches all inferior sessions.
        If any of the sessions fail to close, an error message will be logged, but no exception will be raised.
        The instance will no longer be usable afterward.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _add_inferior(self, session: pyuavcan.transport.Session) -> None:
        """
        If the new session is already an inferior, this method does nothing.
        If anything goes wrong during the initial setup, the inferior will not be added and
        an appropriate exception will be raised.

        This method is intended to be invoked by the transport class.
        The Python's type system does not allow us to concisely define module-internal APIs.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _close_inferior(self, session_index: int) -> None:
        """
        If the index is out of range, this method does nothing.
        Removal always succeeds regardless of any exceptions raised.

        Like its counterpart, this method is supposed to be invoked by the transport class.
        """
        raise NotImplementedError
