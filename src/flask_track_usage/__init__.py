# Copyright (c) 2013 Steve Milner
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     (1) Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#
#     (2) Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in
#     the documentation and/or other materials provided with the
#     distribution.
#
#     (3)The name of the author may not be used to
#     endorse or promote products derived from this software without
#     specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
"""
Basic metrics tracking with Flask.
"""

import datetime
import json
import urllib

from flask import _request_ctx_stack, g

__version__ = '0.0.5'
__author__ = 'Steve Milner'
__license__ = 'MBSD'


class TrackUsage(object):
    """
    Tracks basic usage of Flask applications.
    """

    def __init__(self, app=None, storage=None):
        """
        Create the instance.

        :Parameters:
           - `app`: Optional app to use.
           - `storage`: If app is set you must pass the storage callable now.
        """
        self._exclude_views = set()
        self._include_views = set()

        if app is not None and storage is not None:
            self.init_app(app, storage)

    def init_app(self, app, storage):
        """
        Initialize the instance with the app.

        :Parameters:
           - `app`: Application to work with.
           - `storage`: The storage callable which will store result.
        """
        self.app = app
        self._storage = storage
        self._use_freegeoip = app.config.get(
            'TRACK_USAGE_USE_FREEGEOIP', False)
        self._type = app.config.get(
            'TRACK_USAGE_INCLUDE_OR_EXCLUDE_VIEWS', 'exclude')

        if self._type not in ('include', 'exclude'):
            raise NotImplementedError(
                'You must set include or exclude type.')
        app.before_request(self.before_request)
        app.after_request(self.after_request)

    def before_request(self):
        """
        Done before every request that is in scope.
        """
        ctx = _request_ctx_stack.top
        view_func = self.app.view_functions.get(ctx.request.endpoint)
        if self._type == 'exclude':
            if view_func in self._exclude_views:
                return
        elif self._type == 'include':
            if view_func not in self._include_views:
                return
        else:
            raise NotImplementedError(
                'You must set include or exclude type.')
        g.start_time = datetime.datetime.utcnow()

    def after_request(self, response):
        """
        The heavy lifter. This method collects the majority of data
        and passes it off for storage.

        :Parameters:
           - `response`: The response on it's way to the client.
        """
        ctx = _request_ctx_stack.top
        view_func = self.app.view_functions.get(ctx.request.endpoint)
        if self._type == 'exclude':
            if view_func in self._exclude_views:
                return response
        elif self._type == 'include':
            if view_func not in self._include_views:
                return response
        else:
            raise NotImplementedError(
                'You must set include or exclude type.')

        now = datetime.datetime.utcnow()
        speed = None
        try:
            speed = (now - g.start_time).total_seconds()
        except:
            # Older python versions don't have total_seconds()
            speed_result = (now - g.start_time)
            speed = float("%s.%s" % (
                speed_result.seconds, speed_result.microseconds))

        # Try to be smart and get the right IP address
        remote_addr = ctx.request.remote_addr
        if ctx.request.headers.get('X-Forwarded-For', None):
            remote_addr = ctx.request.headers['X-Forwarded-For']

        data = {
            'url': ctx.request.url,
            'user_agent': ctx.request.user_agent,
            'blueprint': ctx.request.blueprint,
            'view_args': ctx.request.view_args,
            'status': response.status_code,
            'remote_addr': remote_addr,
            'authorization': bool(ctx.request.authorization),
            'ip_info': None,
            'path': ctx.request.path,
            'speed': float(speed),
            'date': int(now.strftime('%s'))
        }
        if self._use_freegeoip:
            ip_info = json.loads(urllib.urlopen(
                'http://freegeoip.net/json/%s' % urllib.quote_plus(
                    remote_addr)).read())
            data['ip_info'] = ip_info

        self._storage(data)
        return response

    def exclude(self, view):
        """
        Excludes a view from tracking if we are in exclude mode.

        :Parameters:
           - `view`: The view to exclude.
        """
        self._exclude_views.add(view)

    def include(self, view):
        """
        Includes a view from tracking if we are in include mode.

        :Parameters:
           - `view`: The view to include.
        """
        self._include_views.add(view)


if __name__ == '__main__':
    # Example
    from flask import Flask
    app = Flask(__name__)

    # Set the configuration items manually for the example
    app.config['TRACK_USAGE_USE_FREEGEOIP'] = False
    app.config['TRACK_USAGE_INCLUDE_OR_EXCLUDE_VIEWS'] = 'include'

    # We will just print out the data for the example
    from flask_track_usage.storage.printer import PrintStorage

    # Make an instance of the extension
    t = TrackUsage(app, PrintStorage())

    # Include the view in the metrics
    @t.include
    @app.route('/')
    def index():
        return "Hello"

    # Run the application!
    app.run(debug=True)
