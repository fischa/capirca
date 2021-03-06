# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unit test for Palo Alto Firewalls acl rendering module."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from capirca.lib import aclgenerator
from capirca.lib import nacaddr
from capirca.lib import naming
from capirca.lib import paloaltofw
from capirca.lib import policy
import mock

GOOD_HEADER_1 = """
header {
  comment:: "This is a test acl with a comment"
  target:: paloalto from-zone trust to-zone untrust
}
"""

GOOD_HEADER_2 = """
header {
  comment:: "This is a test acl with a comment"
  target:: paloalto from-zone all to-zone all
}
"""
BAD_HEADER_1 = """
header {
  comment:: "This header has two address families"
  target:: paloalto from-zone trust to-zone untrust inet6 mixed
}
"""

GOOD_TERM_1 = """
term good-term-1 {
  comment:: "This header is very very very very very very very very very very very very very very very very very very very very large"
  destination-address:: FOOBAR
  destination-port:: SMTP
  protocol:: tcp
  action:: accept
}
"""
GOOD_TERM_2 = """
term good-term-4 {
  destination-address:: SOME_HOST
  protocol:: tcp
  pan-application:: ssl http
  action:: accept
}
"""
GOOD_TERM_3 = """
term only-pan-app {
  pan-application:: ssl
  action:: accept
}
"""
GOOD_TERM_4_STATELESS_REPLY = """
term good-term-stateless-reply {
  comment:: "ThisIsAStatelessReply"
  destination-address:: SOME_HOST
  protocol:: tcp
  pan-application:: ssl http
  action:: accept
}
"""

TCP_ESTABLISHED_TERM = """
term tcp-established {
  destination-address:: SOME_HOST
  protocol:: tcp
  option:: tcp-established
  action:: accept
}
"""

UDP_ESTABLISHED_TERM = """
term udp-established-term {
  destination-address:: SOME_HOST
  protocol:: udp
  option:: established
  action:: accept
}
"""

UNSUPPORTED_OPTION_TERM = """
term unsupported-option-term {
  destination-address:: SOME_HOST
  protocol:: udp
  option:: inactive
  action:: accept
}
"""

EXPIRED_TERM_1 = """
term expired_test {
  expiration:: 2000-1-1
  action:: deny
}
"""

EXPIRING_TERM = """
term is_expiring {
  expiration:: %s
  action:: accept
}
"""

ICMP_TYPE_TERM_1 = """
term test-icmp {
  protocol:: icmp
  icmp-type:: echo-request echo-reply
  action:: accept
}
"""

IPV6_ICMP_TERM = """
term test-ipv6_icmp {
  protocol:: icmpv6
  action:: accept
}
"""

BAD_ICMP_TERM_1 = """
term test-icmp-type {
  icmp-type:: echo-request echo-reply
  action:: accept
}
"""

ICMP_ONLY_TERM_1 = """
term test-icmp-only {
  protocol:: icmp
  action:: accept
}
"""

MULTIPLE_PROTOCOLS_TERM = """
term multi-proto {
  protocol:: tcp udp icmp
  action:: accept
}
"""

DEFAULT_TERM_1 = """
term default-term-1 {
  action:: deny
}
"""

TIMEOUT_TERM = """
term timeout-term {
  protocol:: icmp
  icmp-type:: echo-request
  timeout:: 77
  action:: accept
}
"""

LOGGING_DISABLED = """
term test-disabled-log {
  comment:: "Testing disabling logging for tcp."
  protocol:: tcp
  logging:: disable
  action:: accept
}
"""

LOGGING_BOTH_TERM = """
term test-log-both {
  comment:: "Testing enabling log-both for tcp."
  protocol:: tcp
  logging:: log-both
  action:: accept
}
"""

LOGGING_TRUE_KEYWORD = """
term test-true-log {
  comment:: "Testing enabling logging for udp with true keyword."
  protocol:: udp
  logging:: true
  action:: accept
}
"""

LOGGING_PYTRUE_KEYWORD = """
term test-pytrue-log {
  comment:: "Testing enabling logging for udp with True keyword."
  protocol:: udp
  logging:: True
  action:: accept
}
"""

LOGGING_SYSLOG_KEYWORD = """
term test-syslog-log {
  comment:: "Testing enabling logging for udp with syslog keyword."
  protocol:: udp
  logging:: syslog
  action:: accept
}
"""

LOGGING_LOCAL_KEYWORD = """
term test-local-log {
  comment:: "Testing enabling logging for udp with local keyword."
  protocol:: udp
  logging:: local
  action:: accept
}
"""

ACTION_ACCEPT_TERM = """
term test-accept-action {
  comment:: "Testing accept action for tcp."
  protocol:: tcp
  action:: accept
}
"""

ACTION_COUNT_TERM = """
term test-count-action {
  comment:: "Testing unsupported count action for tcp."
  protocol:: tcp
  action:: count
}
"""

ACTION_NEXT_TERM = """
term test-next-action {
  comment:: "Testing unsupported next action for tcp."
  protocol:: tcp
  action:: next
}
"""

ACTION_DENY_TERM = """
term test-deny-action {
  comment:: "Testing deny action for tcp."
  protocol:: tcp
  action:: deny
}
"""

ACTION_REJECT_TERM = """
term test-reject-action {
  comment:: "Testing reject action for tcp."
  protocol:: tcp
  action:: reject
}
"""

ACTION_RESET_TERM = """
term test-reset-action {
  comment:: "Testing reset action for tcp."
  protocol:: tcp
  action:: reject-with-tcp-rst
}
"""

SUPPORTED_TOKENS = frozenset({
    'action',
    'comment',
    'destination_address',
    'destination_address_exclude',
    'destination_port',
    'expiration',
    'icmp_type',
    'logging',
    'name',
    'option',
    'owner',
    'platform',
    'protocol',
    'source_address',
    'source_address_exclude',
    'source_port',
    'stateless_reply',
    'timeout',
    'pan_application',
    'translated',
})

SUPPORTED_SUB_TOKENS = {
    'action': {'accept', 'deny', 'reject', 'reject-with-tcp-rst'},
    'option': {'established', 'tcp-established'},
    'icmp_type': {
        'alternate-address',
        'certification-path-advertisement',
        'certification-path-solicitation',
        'conversion-error',
        'destination-unreachable',
        'echo-reply',
        'echo-request',
        'mobile-redirect',
        'home-agent-address-discovery-reply',
        'home-agent-address-discovery-request',
        'icmp-node-information-query',
        'icmp-node-information-response',
        'information-request',
        'inverse-neighbor-discovery-advertisement',
        'inverse-neighbor-discovery-solicitation',
        'mask-reply',
        'mask-request',
        'information-reply',
        'mobile-prefix-advertisement',
        'mobile-prefix-solicitation',
        'multicast-listener-done',
        'multicast-listener-query',
        'multicast-listener-report',
        'multicast-router-advertisement',
        'multicast-router-solicitation',
        'multicast-router-termination',
        'neighbor-advertisement',
        'neighbor-solicit',
        'packet-too-big',
        'parameter-problem',
        'redirect',
        'redirect-message',
        'router-advertisement',
        'router-renumbering',
        'router-solicit',
        'router-solicitation',
        'source-quench',
        'time-exceeded',
        'timestamp-reply',
        'timestamp-request',
        'unreachable',
        'version-2-multicast-listener-report',
    },
}

# Print a info message when a term is set to expire in that many weeks.
# This is normally passed from command line.
EXP_INFO = 2

_IPSET = [nacaddr.IP('10.0.0.0/8'), nacaddr.IP('2001:4860:8000::/33')]
_IPSET2 = [nacaddr.IP('10.23.0.0/22'), nacaddr.IP('10.23.0.6/23', strict=False)]
_IPSET3 = [nacaddr.IP('10.23.0.0/23')]


class PaloAltoFWTest(unittest.TestCase):

  def setUp(self):
    super(PaloAltoFWTest, self).setUp()
    self.naming = mock.create_autospec(naming.Naming)

  def testTermAndFilterName(self):
    self.naming.GetNetAddr.return_value = _IPSET
    self.naming.GetServiceByProto.return_value = ['25']

    paloalto = paloaltofw.PaloAltoFW(
        policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_1, self.naming), EXP_INFO)
    output = str(paloalto)
    self.assertIn('<entry name="good-term-1">', output, output)

    self.naming.GetNetAddr.assert_called_once_with('FOOBAR')
    self.naming.GetServiceByProto.assert_called_once_with('SMTP', 'tcp')

  def testDefaultDeny(self):
    paloalto = paloaltofw.PaloAltoFW(
        policy.ParsePolicy(GOOD_HEADER_1 + DEFAULT_TERM_1, self.naming),
        EXP_INFO)
    output = str(paloalto)
    self.assertIn('<action>deny</action>', output, output)

  def testIcmpTypes(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + ICMP_TYPE_TERM_1, self.naming)
    output = str(paloaltofw.PaloAltoFW(pol, EXP_INFO))
    self.assertIn('<member>icmp-echo-request</member>', output, output)
    self.assertIn('<member>icmp-echo-reply</member>', output, output)

  def testBadICMP(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + BAD_ICMP_TERM_1, self.naming)
    self.assertRaises(paloaltofw.UnsupportedFilterError, paloaltofw.PaloAltoFW,
                      pol, EXP_INFO)

  def testICMPProtocolOnly(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + ICMP_ONLY_TERM_1, self.naming)
    output = str(paloaltofw.PaloAltoFW(pol, EXP_INFO))
    self.assertIn('<member>icmp</member>', output, output)

  def testSkipStatelessReply(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_4_STATELESS_REPLY,
                             self.naming)

    # Add stateless_reply to terms, there is no current way to include it in the
    # term definition.
    _, terms = pol.filters[0]
    for term in terms:
      term.stateless_reply = True

    output = str(paloaltofw.PaloAltoFW(pol, EXP_INFO))
    self.assertNotIn('good-term-stateless-reply', output, output)

  def testSkipEstablished(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + TCP_ESTABLISHED_TERM, self.naming)
    output = str(paloaltofw.PaloAltoFW(pol, EXP_INFO))
    self.assertNotIn('tcp-established', output, output)
    pol = policy.ParsePolicy(GOOD_HEADER_1 + UDP_ESTABLISHED_TERM, self.naming)
    output = str(paloaltofw.PaloAltoFW(pol, EXP_INFO))
    self.assertNotIn('udp-established-term', output, output)

  def testUnsupportedOptions(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + UNSUPPORTED_OPTION_TERM,
                             self.naming)
    self.assertRaises(aclgenerator.UnsupportedFilterError,
                      paloaltofw.PaloAltoFW, pol, EXP_INFO)

  def testBuildTokens(self):
    self.naming.GetServiceByProto.side_effect = [['25'], ['26']]
    pol1 = paloaltofw.PaloAltoFW(
        policy.ParsePolicy(GOOD_HEADER_1 + GOOD_TERM_2, self.naming), EXP_INFO)
    st, sst = pol1._BuildTokens()
    self.assertEqual(st, SUPPORTED_TOKENS)
    self.assertEqual(sst, SUPPORTED_SUB_TOKENS)

  def testLoggingBoth(self):
    paloalto = paloaltofw.PaloAltoFW(
        policy.ParsePolicy(GOOD_HEADER_1 + LOGGING_BOTH_TERM, self.naming),
        EXP_INFO)
    output = str(paloalto)
    self.assertIn('<log-start>yes</log-start>', output, output)
    self.assertIn('<log-end>yes</log-end>', output, output)

  def testDisableLogging(self):
    paloalto = paloaltofw.PaloAltoFW(
        policy.ParsePolicy(GOOD_HEADER_1 + LOGGING_DISABLED, self.naming),
        EXP_INFO)
    output = str(paloalto)
    self.assertIn('<log-start>no</log-start>', output, output)
    self.assertIn('<log-end>no</log-end>', output, output)

  def testLogging(self):
    for term in [
        LOGGING_SYSLOG_KEYWORD, LOGGING_LOCAL_KEYWORD, LOGGING_PYTRUE_KEYWORD,
        LOGGING_TRUE_KEYWORD
    ]:
      pol = paloaltofw.PaloAltoFW(
          policy.ParsePolicy(GOOD_HEADER_1 + term, self.naming), EXP_INFO)
      output = str(pol)
      self.assertNotIn('<log-start>yes</log-start>', output, output)
      self.assertIn('<log-end>yes</log-end>', output, output)

  def testAcceptAction(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + ACTION_ACCEPT_TERM, self.naming)
    output = str(paloaltofw.PaloAltoFW(pol, EXP_INFO))
    self.assertIn('<action>allow</action>', output, output)

  def testDenyAction(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + ACTION_DENY_TERM, self.naming)
    output = str(paloaltofw.PaloAltoFW(pol, EXP_INFO))
    self.assertIn('<action>deny</action>', output, output)

  def testRejectAction(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + ACTION_REJECT_TERM, self.naming)
    output = str(paloaltofw.PaloAltoFW(pol, EXP_INFO))
    self.assertIn('<action>reset-client</action>', output, output)

  def testResetAction(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + ACTION_RESET_TERM, self.naming)
    output = str(paloaltofw.PaloAltoFW(pol, EXP_INFO))
    self.assertIn('<action>reset-client</action>', output, output)

  def testCountAction(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + ACTION_COUNT_TERM, self.naming)
    self.assertRaises(aclgenerator.UnsupportedFilterError,
                      paloaltofw.PaloAltoFW, pol, EXP_INFO)

  def testNextAction(self):
    pol = policy.ParsePolicy(GOOD_HEADER_1 + ACTION_NEXT_TERM, self.naming)
    self.assertRaises(aclgenerator.UnsupportedFilterError,
                      paloaltofw.PaloAltoFW, pol, EXP_INFO)


if __name__ == '__main__':
  unittest.main()
