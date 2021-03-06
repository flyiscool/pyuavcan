#
# Copyright (c) 2019 UAVCAN Development Team
# This software is distributed under the terms of the MIT License.
# Author: Pavel Kirienko <pavel.kirienko@zubax.com>
#

import typing
import pytest

# The fixture is imported here to make it visible to other tests in this suite.
from .dsdl.conftest import generated_packages as generated_packages  # noqa


def pytest_collection_modifyitems(items: typing.Iterable[pytest.Item]) -> None:
    # https://docs.pytest.org/en/latest/example/simple.html
    from . import SKIP_SLOW
    if SKIP_SLOW:  # pragma: no cover
        skip_slow = pytest.mark.skip(reason='SKIP_SLOW is set')
        for item in items:
            _, _, name = item.reportinfo()
            if name.startswith('_unittest_slow_'):
                item.add_marker(skip_slow)
