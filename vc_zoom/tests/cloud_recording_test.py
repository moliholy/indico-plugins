# This file is part of the Indico plugins.
# Copyright (C) 2020 - 2026 CERN and ENEA
#
# The Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License;
# see the LICENSE file for more details.

from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from flask import session

from indico.web.forms.base import FormDefaults

from indico_vc_zoom.forms import VCRoomForm


TZ = ZoneInfo('Europe/Zurich')


@pytest.fixture
def event(create_event, zoom_api):
    return create_event(
        creator=zoom_api['user'],
        start_dt=datetime(2024, 3, 1, 16, 0, tzinfo=TZ),
        end_dt=datetime(2024, 3, 1, 18, 0, tzinfo=TZ),
        title='Test Event #1',
        creator_has_privileges=True,
    )


@pytest.fixture
def allow_cloud_recording(zoom_plugin):
    zoom_plugin.settings.set('allow_cloud_recording', True)


@contextmanager
def _make_form(zoom_plugin, app, event, user, formdata=None):
    defaults = FormDefaults({
        'name': 'Test',
        'password': '12345678',
        'host_choice': 'myself',
        'description': '',
        'meeting_type': 'regular',
        'linking': 'event',
        'mute_audio': True,
        'mute_host_video': True,
        'mute_participant_video': True,
        'waiting_room': False,
        'alternative_hosts': [],
        'host': None,
    })
    with app.test_request_context(method='POST', data=formdata), zoom_plugin.plugin_context():
        session.set_session_user(user)
        yield VCRoomForm(prefix='vc-', obj=defaults, event=event, vc_room=None)


def _zoom_meeting(meeting_id, auto_recording):
    return {
        'id': meeting_id,
        'join_url': 'https://example.com/kitties',
        'start_url': 'https://example.com/puppies',
        'password': '13371337',
        'host_id': 'don.orange@megacorp.xyz',
        'topic': 'Zoom Meeting',
        'agenda': 'nothing to add',
        'settings': {
            'host_video': False,
            'mute_upon_entry': True,
            'participant_video': False,
            'waiting_room': False,
            'alternative_hosts': '',
            'approval_type': 2,
            'auto_recording': auto_recording,
        },
    }


@pytest.mark.usefixtures('allow_cloud_recording')
def test_form_stores_cloud_recording(zoom_plugin, app, event, zoom_user):
    with _make_form(zoom_plugin, app, event, zoom_user, formdata={'vc-cloud_recording': 'y'}) as form:
        assert form.data.get('cloud_recording') is True


def test_form_omits_cloud_recording_when_not_allowed(zoom_plugin, app, event, zoom_user):
    with _make_form(zoom_plugin, app, event, zoom_user) as form:
        assert 'cloud_recording' not in form


@pytest.mark.usefixtures('allow_cloud_recording')
@pytest.mark.parametrize('meeting_type', ('regular', 'webinar'))
def test_update_data_stores_cloud_recording(create_zoom_meeting, zoom_plugin, event, meeting_type):
    vc_room = create_zoom_meeting(event, 'event')
    vc_room.data['meeting_type'] = meeting_type

    zoom_plugin.update_data_vc_room(vc_room, {'cloud_recording': True})

    assert vc_room.data.get('cloud_recording') is True


@pytest.mark.usefixtures('allow_cloud_recording')
@pytest.mark.parametrize(('cloud_recording', 'auto_recording'), ((True, 'cloud'), (False, 'none')))
def test_create_room_sends_auto_recording(create_zoom_meeting, zoom_plugin, zoom_api, event, cloud_recording,
                                          auto_recording):
    vc_room = create_zoom_meeting(event, 'event')
    vc_room.data['cloud_recording'] = cloud_recording
    zoom_api['create_meeting'].reset_mock()

    zoom_plugin.create_room(vc_room, event)

    assert zoom_api['create_meeting'].call_args.kwargs['settings'].get('auto_recording') == auto_recording


@pytest.mark.usefixtures('allow_cloud_recording')
def test_create_webinar_sends_auto_recording(mocker, create_zoom_meeting, zoom_plugin, zoom_api, event):
    create_webinar = mocker.patch('indico_vc_zoom.plugin.ZoomIndicoClient.create_webinar')
    create_webinar.side_effect = zoom_api['create_meeting'].side_effect
    vc_room = create_zoom_meeting(event, 'event')
    vc_room.data['meeting_type'] = 'webinar'
    vc_room.data['cloud_recording'] = True

    zoom_plugin.create_room(vc_room, event)

    assert create_webinar.call_args.kwargs['settings'].get('auto_recording') == 'cloud'


def test_create_room_omits_auto_recording_when_not_allowed(create_zoom_meeting, zoom_plugin, zoom_api, event):
    vc_room = create_zoom_meeting(event, 'event')
    zoom_api['create_meeting'].reset_mock()

    zoom_plugin.create_room(vc_room, event)

    assert 'auto_recording' not in zoom_api['create_meeting'].call_args.kwargs['settings']


@pytest.mark.usefixtures('allow_cloud_recording')
@pytest.mark.parametrize(('cloud_recording', 'zoom_auto_recording', 'auto_recording'), (
    (True, 'none', 'cloud'),
    (True, 'local', 'cloud'),
    (False, 'cloud', 'none'),
))
def test_update_room_pushes_auto_recording(mocker, create_zoom_meeting, zoom_plugin, zoom_api, event, cloud_recording,
                                           zoom_auto_recording, auto_recording):
    vc_room = create_zoom_meeting(event, 'event')
    vc_room.data['cloud_recording'] = cloud_recording
    mocker.patch('indico_vc_zoom.plugin.ZoomIndicoClient.get_meeting',
                 side_effect=lambda id_, *a, **kw: _zoom_meeting(id_, zoom_auto_recording))
    api_mock = mocker.patch('indico_vc_zoom.util.ZoomIndicoClient.update_meeting')

    zoom_plugin.update_room(vc_room, event)

    api_mock.assert_called_once_with(vc_room.data['zoom_id'], {'settings': {'auto_recording': auto_recording}})


@pytest.mark.usefixtures('allow_cloud_recording')
@pytest.mark.parametrize(('cloud_recording', 'zoom_auto_recording'), (
    (True, 'cloud'),
    (False, 'none'),
    (False, 'local'),
))
def test_update_room_keeps_auto_recording(mocker, create_zoom_meeting, zoom_plugin, zoom_api, event, cloud_recording,
                                          zoom_auto_recording):
    vc_room = create_zoom_meeting(event, 'event')
    vc_room.data['cloud_recording'] = cloud_recording
    mocker.patch('indico_vc_zoom.plugin.ZoomIndicoClient.get_meeting',
                 side_effect=lambda id_, *a, **kw: _zoom_meeting(id_, zoom_auto_recording))
    api_mock = mocker.patch('indico_vc_zoom.util.ZoomIndicoClient.update_meeting')

    zoom_plugin.update_room(vc_room, event)

    api_mock.assert_not_called()


def test_update_room_ignores_auto_recording_when_not_allowed(mocker, create_zoom_meeting, zoom_plugin, zoom_api, event):
    vc_room = create_zoom_meeting(event, 'event')
    mocker.patch('indico_vc_zoom.plugin.ZoomIndicoClient.get_meeting',
                 side_effect=lambda id_, *a, **kw: _zoom_meeting(id_, 'cloud'))
    api_mock = mocker.patch('indico_vc_zoom.util.ZoomIndicoClient.update_meeting')

    zoom_plugin.update_room(vc_room, event)

    api_mock.assert_not_called()


@pytest.mark.parametrize(('auto_recording', 'cloud_recording'), (('cloud', True), ('local', False), ('none', False)))
def test_refresh_room_reads_cloud_recording(mocker, create_zoom_meeting, zoom_plugin, zoom_api, event, auto_recording,
                                            cloud_recording):
    vc_room = create_zoom_meeting(event, 'event')
    mocker.patch('indico_vc_zoom.plugin.ZoomIndicoClient.get_meeting',
                 side_effect=lambda id_, *a, **kw: _zoom_meeting(id_, auto_recording))

    zoom_plugin.refresh_room(vc_room, event)

    assert vc_room.data.get('cloud_recording') is cloud_recording
