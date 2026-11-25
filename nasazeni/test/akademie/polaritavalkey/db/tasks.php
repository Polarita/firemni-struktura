<?php
// SPDX-License-Identifier: GPL-3.0-or-later
defined('MOODLE_INTERNAL') || die();
$tasks = [[
    'classname' => \cachestore_polaritavalkey\task\expiry::class,
    'minute' => 'R',
    'hour' => '*',
    'day' => '*',
    'month' => '*',
    'dayofweek' => '*',
]];
