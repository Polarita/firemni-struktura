<?php
// SPDX-License-Identifier: GPL-3.0-or-later
namespace cachestore_polaritavalkey\task;

use core_cache\factory;
use core_cache\helper;

/** Remove expired entries from the Academy's native Redis hashes. */
class expiry extends \core\task\scheduled_task {
    public function get_name(): string {
        return get_string('task_ttl', 'cachestore_redis');
    }

    public function execute(): void {
        $factory = factory::instance();
        $config = $factory->create_config_instance();
        foreach ($config->get_all_stores() as $name => $instance) {
            if ($instance['plugin'] !== 'polaritavalkey') {
                continue;
            }
            foreach ($config->get_definitions_by_store($name) as $entry) {
                if (empty($entry['ttl']) || !empty($entry['requireidentifiers'])) {
                    continue;
                }
                $definition = $factory->create_definition($entry['component'], $entry['area']);
                foreach (helper::get_cache_stores($definition) as $store) {
                    if ($store instanceof \cachestore_polaritavalkey && $store->my_name() === $name) {
                        $store->expire_ttl();
                    }
                }
            }
        }
    }
}
