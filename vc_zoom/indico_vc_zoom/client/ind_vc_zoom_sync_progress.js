// This file is part of the Indico plugins.
// Copyright (C) 2020 - 2026 CERN and ENEA
//
// The Indico plugins are free software; you can redistribute
// them and/or modify them under the terms of the MIT License;
// see the LICENSE file for more details.

import {Translate} from 'indico/react/i18n';
import {indicoAxios} from 'indico/utils/axios';

import './ind_vc_zoom_sync_progress.scss';

const POLL_INTERVAL = 2000;
const MAX_POLLS = 450; // ~15 minutes before falling back to a manual-refresh hint

function progressLabel({state, action, done, total}) {
  if (state === 'queued' || !total) {
    return Translate.string('Starting…');
  }
  return action === 'deregister'
    ? Translate.string('Removing {done}/{total}…', {done, total})
    : Translate.string('Syncing {done}/{total}…', {done, total});
}

function renderProgress($actions, text, spinning = true) {
  let $progress = $actions.find('.vc-zoom-sync-progress');
  if (!$progress.length) {
    $actions.children('.js-zoom-registrant-action').hide();
    $progress = $(
      '<span class="vc-zoom-sync-progress">' +
        '<span class="icon-spinner vc-zoom-sync-spinner"></span> ' +
        '<span class="vc-zoom-sync-progress-text"></span>' +
        '</span>'
    );
    $actions.append($progress);
  }
  $progress.toggleClass('vc-zoom-sync-idle', !spinning);
  $progress.find('.vc-zoom-sync-progress-text').text(text);
}

function poll($actions, statusUrl, count) {
  if (count >= MAX_POLLS) {
    renderProgress($actions, Translate.string('Still running. Refresh to see the result.'), false);
    return;
  }
  indicoAxios
    .get(statusUrl)
    .then(({data}) => {
      if (data.state === 'done') {
        location.reload();
        return;
      }
      renderProgress($actions, progressLabel(data));
      setTimeout(() => poll($actions, statusUrl, count + 1), POLL_INTERVAL);
    })
    .catch(() => setTimeout(() => poll($actions, statusUrl, count + 1), POLL_INTERVAL));
}

// A sync/deregister action was accepted: show live progress instead of reloading the page.
$(document).on('declarative:success', '.js-zoom-registrant-action', function (evt) {
  evt.preventDefault();
  const $actions = $(this).closest('.zoom-registrant-actions');
  renderProgress($actions, Translate.string('Starting…'));
  poll($actions, $actions.data('status-url'), 0);
});

// Resume the live display if an operation is already running when the page loads.
$(() => {
  $('.zoom-registrant-actions').each(function () {
    const $actions = $(this);
    const statusUrl = $actions.data('status-url');
    if (!statusUrl) {
      return;
    }
    indicoAxios.get(statusUrl).then(({data}) => {
      if (data.state === 'running' || data.state === 'queued') {
        renderProgress($actions, progressLabel(data));
        poll($actions, statusUrl, 0);
      }
    });
  });
});
