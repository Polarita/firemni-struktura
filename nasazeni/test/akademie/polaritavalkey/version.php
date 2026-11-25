<?php
// SPDX-License-Identifier: GPL-3.0-or-later
defined('MOODLE_INTERNAL') || die();
$plugin->component = 'cachestore_polaritavalkey';
$plugin->version = 2026112500;
$plugin->requires = 2026100200;
$plugin->dependencies = ['cachestore_redis' => 2026100500];
