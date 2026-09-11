# This file is part of the Indico plugins.
# Copyright (C) 2020 - 2026 CERN and ENEA
#
# The Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License;
# see the LICENSE file for more details.

import pytest

from indico_vc_zoom.plugin import PluginSettingsForm


@pytest.mark.usefixtures('request_context')
def test_settings_form_shows_webhook_token_when_not_in_config():
    assert 'webhook_token' in PluginSettingsForm()


@pytest.mark.usefixtures('request_context')
def test_settings_form_hides_webhook_token_when_in_config(patch_indico_config):
    patch_indico_config('PLUGIN_VC_ZOOM_WEBHOOK_TOKEN', 'config-token')
    assert 'webhook_token' not in PluginSettingsForm()
