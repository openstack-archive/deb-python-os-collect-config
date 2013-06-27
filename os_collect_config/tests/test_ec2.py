# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import fixtures
import httplib2
import testtools
from testtools import matchers
import urlparse
import uuid

from os_collect_config import collect
from os_collect_config import ec2
from os_collect_config import exc


META_DATA = {'local-ipv4':     '192.0.2.1',
             'reservation-id': str(uuid.uuid1()),
             'local-hostname': 'foo',
             'ami-launch-index': '0',
             'public-hostname': 'foo',
             'hostname': 'foo',
             'ami-id': str(uuid.uuid1()),
             'instance-action': 'none',
             'public-ipv4': '192.0.2.1',
             'instance-type': 'flavor.small',
             'placement/': 'availability-zone',
             'placement/availability-zone': 'foo-az',
             'mpi/': 'foo-keypair',
             'mpi/foo-keypair': '192.0.2.1 slots=1',
             'block-device-mapping/': "ami\nroot\nephemeral0",
             'block-device-mapping/ami': 'vda',
             'block-device-mapping/root': '/dev/vda',
             'block-device-mapping/ephemeral0': '/dev/vdb',
             'public-keys/': '0=foo-keypair',
             'public-keys/0': 'openssh-key',
             'public-keys/0/': 'openssh-key',
             'public-keys/0/openssh-key': 'ssh-rsa AAAAAAAAABBBBBBBBCCCCCCCC',
             'instance-id': str(uuid.uuid1())}


class FakeResponse(dict):
    status = 200


class FakeHttp(object):

    def request(self, url):
        url = urlparse.urlparse(url)

        if url.path == '/latest/meta-data/':
            # Remove keys which have anything after /
            ks = [x for x in META_DATA.keys() if ('/' not in x
                                                  or not len(x.split('/')[1]))]
            return (FakeResponse(), "\n".join(ks))

        path = url.path
        path = path.replace('/latest/meta-data/', '')
        return (FakeResponse(), META_DATA[path])


class FakeFailHttp(object):
    def request(self, url):
        raise httplib2.socks.HTTPError(403, 'Forbidden')


class TestCollect(testtools.TestCase):
    def setUp(self):
        super(TestCollect, self).setUp()
        self.log = self.useFixture(fixtures.FakeLogger())

    def test_collect_ec2(self):
        self.useFixture(
            fixtures.MonkeyPatch('os_collect_config.ec2.h', FakeHttp()))
        collect.setup_conf()
        ec2_md = ec2.collect()
        self.assertThat(ec2_md, matchers.IsInstance(dict))

        for k in ('public-ipv4', 'instance-id', 'hostname'):
            self.assertIn(k, ec2_md)
            self.assertEquals(ec2_md[k], META_DATA[k])

        self.assertEquals(ec2_md['block-device-mapping']['ami'], 'vda')

        # SSH keys are special cases
        self.assertEquals(
            {'0': {'openssh-key': 'ssh-rsa AAAAAAAAABBBBBBBBCCCCCCCC'}},
            ec2_md['public-keys'])
        self.assertEquals('', self.log.output)

    def test_collect_ec2_fail(self):
        self.useFixture(
            fixtures.MonkeyPatch(
                'os_collect_config.ec2.h', FakeFailHttp()))
        collect.setup_conf()
        self.assertRaises(exc.Ec2MetadataNotAvailable, ec2.collect)
        self.assertIn('Forbidden', self.log.output)
