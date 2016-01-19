# -*- coding: utf-8 -*-

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from purpleyard import gitlogs
from purpleyard.tests import base


class TestNode(base.TestCase):
    def setUp(self):
        super(TestNode, self).setUp()
        self.node = gitlogs.Node("name", "company", "email")

    def test_is_core(self):
        self.node.review_count = 25
        self.assertTrue(self.node.is_core())

    def test_is_not_core(self):
        self.node.review_count = 1
        self.assertFalse(self.node.is_core())
