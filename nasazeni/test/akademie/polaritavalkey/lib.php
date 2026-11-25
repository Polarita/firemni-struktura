<?php
// SPDX-License-Identifier: GPL-3.0-or-later
defined('MOODLE_INTERNAL') || die();
require_once(__DIR__ . '/../redis/lib.php');

/** Redis store with the Academy's Valkey endpoint and OpenBao identity. */
class cachestore_polaritavalkey extends cachestore_redis {
    public function __construct($name, array $configuration = []) {
        $secret = file_get_contents('/run/secrets/valkey-akademie');
        if ($secret === false || !preg_match('/^[A-Za-z0-9_-]+$/D', $secret)) {
            throw new RuntimeException('Chybí přihlašovací údaj Akademie pro Valkey.');
        }
        parent::__construct($name, [
            'server' => '10.239.33.13:6379',
            'encryption' => true,
            'cafile' => '/etc/polarita-akademie/valkey.crt',
            'password' => ['akademie', $secret],
            'prefix' => 'akademie:moodle:',
            'connectiontimeout' => 5,
            'readtimeout' => 5,
        ]);
    }

    // The deployment supplies the connection details for every instance.
    public static function config_get_configuration_array($data) {
        return [];
    }

    public static function config_set_edit_form_data(moodleform $editform, array $config) {
    }

    public function store_total_size(): ?int {
        // The shared server cannot attribute its total memory use to this application.
        return null;
    }
}
