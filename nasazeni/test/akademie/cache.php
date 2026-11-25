<?php
// Nastaví sdílenou mezipaměť katalogu a ověří skutečný zápis z Moodle.
define('CLI_SCRIPT', true);
require '/opt/polarita-akademie/current/config.php';

use core_cache\cache;
use core_cache\config_writer;
use core_cache\factory;
use core_cache\helper;

$name = 'ValkeyAkademie';
$areas = ['coursecattree', 'coursecontacts'];
if (($argv[1] ?? '') === '--nastav') {
    $writer = config_writer::instance();
    $stores = $writer->get_all_stores();
    if (!isset($stores[$name])) {
        $writer->add_store_instance($name, 'polaritavalkey');
    } elseif ($stores[$name]['plugin'] !== 'polaritavalkey') {
        throw new RuntimeException('Jméno cache Akademie už používá jiné úložiště.');
    }
    foreach ($areas as $area) {
        $id = 'core/' . $area;
        $stores = array_column(array_filter($writer->get_definition_mappings(),
            fn($item) => $item['definition'] === $id), 'store');
        if ($stores !== [$name]) {
            $writer->set_definition_mappings($id, [$name]);
        }
    }
    exit(0);
}

foreach ($areas as $area) {
    $definition = factory::instance()->create_definition('core', $area);
    $stores = helper::get_cache_stores($definition);
    if (count($stores) !== 1 || !$stores[0] instanceof cachestore_polaritavalkey || !$stores[0]->is_ready()) {
        throw new RuntimeException('Moodle nepřiřadil aktivní Valkey ke katalogu kurzů.');
    }
    $cache = cache::make('core', $area);
    $key = 'polarita_test_' . bin2hex(random_bytes(12));
    $value = bin2hex(random_bytes(16));
    $field = helper::hash_key($key, $definition);
    try {
        if (!$cache->set($key, $value) || $cache->get($key) !== $value) {
            throw new RuntimeException('Moodle nevrátil vloženou hodnotu.');
        }
        $stored = $stores[0]->get($field);
        if ($stored instanceof core_cache\ttl_wrapper && !$stored->has_expired()) {
            $stored = $stored->data;
        }
        if ($stored !== $value) {
            throw new RuntimeException('Zápis z Moodle a přímé čtení z Valkey se liší.');
        }
    } finally {
        $cache->delete($key);
    }
    if ($stores[0]->has($field)) {
        throw new RuntimeException('Po odstranění z Moodle zůstalo pole v úložišti.');
    }
}
echo "Moodle přidělil strom kategorií a kontakty kurzů do Valkey. Zápis, přímé čtení a odstranění přes obě rozhraní prošly.\n";
