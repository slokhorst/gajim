# Copyright (C) 2006 Tomasz Melcer <liori AT exroot.org>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0060: Publish-Subscribe

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.modules import dataforms

from gajim.common import app
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.modules.base import BaseModule


class PubSub(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.publish_options = False

    def pass_disco(self, info):
        if Namespace.PUBSUB_PUBLISH_OPTIONS not in info.features:
            # Remove stored bookmarks accessible to everyone.
            self._con.get_module('Bookmarks').purge_pubsub_bookmarks()
            return
        self._log.info('Discovered Pubsub publish options: %s', info.jid)
        self.publish_options = True

    def send_pb_subscription_query(self, jid, cb, **kwargs):
        if not app.account_is_available(self._account):
            return

        query = nbxmpp.Iq('get', to=jid)
        pb = query.addChild('pubsub', namespace=Namespace.PUBSUB)
        pb.addChild('subscriptions')

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_subscribe(self, jid, node, cb, **kwargs):
        if not app.account_is_available(self._account):
            return

        our_jid = app.get_jid_from_account(self._account)
        query = nbxmpp.Iq('set', to=jid)
        pb = query.addChild('pubsub', namespace=Namespace.PUBSUB)
        pb.addChild('subscribe', {'node': node, 'jid': our_jid})

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_unsubscribe(self, jid, node, cb, **kwargs):
        if not app.account_is_available(self._account):
            return

        our_jid = app.get_jid_from_account(self._account)
        query = nbxmpp.Iq('set', to=jid)
        pb = query.addChild('pubsub', namespace=Namespace.PUBSUB)
        pb.addChild('unsubscribe', {'node': node, 'jid': our_jid})

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_publish(self, jid, node, item,
                        id_=None, options=None, cb=None, **kwargs):
        if not app.account_is_available(self._account):
            return

        if cb is None:
            cb = self._default_callback

        query = nbxmpp.Iq('set', to=jid)
        pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB)
        publish = pubsub.addChild('publish', {'node': node})
        attrs = {}
        if id_:
            attrs = {'id': id_}
        publish.addChild('item', attrs, [item])
        if options:
            publish = pubsub.addChild('publish-options')
            publish.addChild(node=options)

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    @staticmethod
    def get_pb_retrieve_iq(jid, node, item_id=None):
        """
        Get IQ to query items from a node
        """
        query = nbxmpp.Iq('get', to=jid)
        pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB)
        items = pubsub.addChild('items', {'node': node})
        if item_id is not None:
            items.addChild('item', {'id': item_id})
        return query

    def send_pb_retrieve(self, jid, node, item_id=None, cb=None, **kwargs):
        """
        Get items from a node
        """
        if not app.account_is_available(self._account):
            return

        if cb is None:
            cb = self._default_callback

        query = self.get_pb_retrieve_iq(jid, node, item_id)

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_retract(self, jid, node, id_, cb=None, **kwargs):
        """
        Delete item from a node
        """
        if not app.account_is_available(self._account):
            return

        if cb is None:
            cb = self._default_callback

        query = nbxmpp.Iq('set', to=jid)
        pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB)
        retract = pubsub.addChild('retract', {'node': node, 'notify': '1'})
        retract.addChild('item', {'id': id_})

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_purge(self, jid, node, cb=None, **kwargs):
        """
        Purge node: Remove all items
        """
        if not app.account_is_available(self._account):
            return

        if cb is None:
            cb = self._default_callback

        query = nbxmpp.Iq('set', to=jid)
        pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB_OWNER)
        pubsub.addChild('purge', {'node': node})

        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def send_pb_delete(self, jid, node, on_ok=None, on_fail=None):
        """
        Delete node
        """
        if not app.account_is_available(self._account):
            return
        query = nbxmpp.Iq('set', to=jid)
        pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB_OWNER)
        pubsub.addChild('delete', {'node': node})

        def response(_nbxmpp_client, resp, jid, node):
            if resp.getType() == 'result' and on_ok:
                on_ok(jid, node)
            elif on_fail:
                msg = resp.getErrorMsg()
                on_fail(jid, node, msg)

        self._con.connection.SendAndCallForResponse(
            query, response, {'jid': jid, 'node': node})

    def send_pb_create(self, jid, node, cb,
                       configure=False, configure_form=None):
        """
        Create a new node
        """
        if not app.account_is_available(self._account):
            return
        query = nbxmpp.Iq('set', to=jid)
        pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB)
        create = pubsub.addChild('create', {'node': node})
        if configure:
            conf = create.addChild('configure')
            if configure_form is not None:
                conf.addChild(node=configure_form)

        self._con.connection.SendAndCallForResponse(query, cb)

    def send_pb_configure(self, jid, node, form, cb=None, **kwargs):
        if not app.account_is_available(self._account):
            return

        if cb is None:
            cb = self._default_callback

        query = nbxmpp.Iq('set', to=jid)
        pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB_OWNER)
        configure = pubsub.addChild('configure', {'node': node})
        configure.addChild(node=form)

        self._log.info('Send node config for %s', node)
        self._con.connection.SendAndCallForResponse(query, cb, kwargs)

    def request_pb_configuration(self, jid, node):
        if not app.account_is_available(self._account):
            return

        query = nbxmpp.Iq('get', to=jid)
        pubsub = query.addChild('pubsub', namespace=Namespace.PUBSUB_OWNER)
        pubsub.addChild('configure', {'node': node})

        self._log.info('Request node config for %s', node)
        self._con.connection.SendAndCallForResponse(
            query, self._received_pb_configuration, {'node': node})

    def _received_pb_configuration(self, _nbxmpp_client, stanza, node):
        if not nbxmpp.isResultNode(stanza):
            self._log.warning('Error: %s', stanza.getError())
            return

        pubsub = stanza.getTag('pubsub', namespace=Namespace.PUBSUB_OWNER)
        if pubsub is None:
            self._log.warning('Malformed PubSub configure '
                              'stanza (no pubsub node): %s', stanza)
            return

        configure = pubsub.getTag('configure')
        if configure is None:
            self._log.warning('Malformed PubSub configure '
                              'stanza (no configure node): %s', stanza)
            return

        if configure.getAttr('node') != node:
            self._log.warning('Malformed PubSub configure '
                              'stanza (wrong node): %s', stanza)
            return

        form = configure.getTag('x', namespace=Namespace.DATA)
        if form is None:
            self._log.warning('Malformed PubSub configure '
                              'stanza (no form): %s', stanza)
            return

        app.nec.push_incoming_event(PubSubConfigReceivedEvent(
            None, conn=self._con, node=node,
            form=dataforms.extend_form(node=form)))

    def _default_callback(self, _con, stanza, *args, **kwargs):
        if not nbxmpp.isResultNode(stanza):
            self._log.warning('Error: %s', stanza.getError())


class PubSubConfigReceivedEvent(NetworkIncomingEvent):
    name = 'pubsub-config-received'


def get_instance(*args, **kwargs):
    return PubSub(*args, **kwargs), 'PubSub'
