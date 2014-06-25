from datetime import datetime

from pyramid import testing

from pycchdo.log import getLogger
from pycchdo.tests import BaseTest
from pycchdo.models.serial import SerializerDateTime


log = getLogger(__name__)


class TestSerializerDateTime(BaseTest):
    def setUp(self):
        super(TestSerializerDateTime, self).setUp()
        self.dtime = datetime(1900, 1, 2, 3, 4, 5, 6)
        self.output = '{"type": "dt", "val": "1900-01-02T03:04:05.000006"}'

    def test_serialize(self):
        serial = SerializerDateTime.serialize(self.dtime)
        self.assertEqual(self.output, serial)

    def test_deserialize(self):
        deserial = SerializerDateTime.deserialize(self.output)
        self.assertEqual(deserial, self.dtime)
