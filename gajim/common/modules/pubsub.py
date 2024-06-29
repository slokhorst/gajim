# Copyright (C) 2006 Tomasz Melcer <liori AT exroot.org>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0060: Publish-Subscribe

from __future__ import annotations

from typing import Any

from collections.abc import Callable

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import DiscoInfo

from gajim.common import app
from gajim.common import types
from gajim.common.modules.base import BaseModule


class PubSub(BaseModule):

    _nbxmpp_extends = 'PubSub'
    _nbxmpp_methods = [
        'publish',
        'delete',
        'set_node_configuration',
        'get_node_configuration',
        'get_access_model',
        'request_items',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.publish_options = False

    def pass_disco(self, info: DiscoInfo) -> None:
        if Namespace.PUBSUB_PUBLISH_OPTIONS in info.features:
            self._log.info('Discovered Pubsub publish options: %s', info.jid)
            self.publish_options = True

    def send_pb_subscription_query(self,
                                   jid: str,
                                   cb: Callable[..., Any],
                                   **kwargs: Any
                                   ) -> None:
        if not app.account_is_available(self._account):
            return

        query = nbxmpp.Iq('get', to=jid)
        pb = query.addChild('pubsub', namespace=Namespace.PUBSUB)
        pb.addChild('subscriptions')

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_subscribe(self,
                          jid: str,
                          node: str,
                          cb: Callable[..., Any],
                          **kwargs: Any
                          ) -> None:
        if not app.account_is_available(self._account):
            return

        our_jid = app.get_jid_from_account(self._account)
        query = nbxmpp.Iq('set', to=jid)
        pb = query.addChild('pubsub', namespace=Namespace.PUBSUB)
        pb.addChild('subscribe', {'node': node, 'jid': our_jid})

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_unsubscribe(self,
                            jid: str,
                            node: str,
                            cb: Callable[..., Any],
                            **kwargs: Any
                            ) -> None:
        if not app.account_is_available(self._account):
            return

        our_jid = app.get_jid_from_account(self._account)
        query = nbxmpp.Iq('set', to=jid)
        pb = query.addChild('pubsub', namespace=Namespace.PUBSUB)
        pb.addChild('unsubscribe', {'node': node, 'jid': our_jid})

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)
