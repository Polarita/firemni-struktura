<?php
declare(strict_types=1);

function testPassword(string $name): string {
    $path = "/run/secrets/$name";
    $value = file_get_contents($path);
    if ($value === false || !preg_match('/^[A-Za-z0-9_-]+$/D', $value)
            || (fileperms($path) & 0777) !== 0400 || fileowner($path) !== 33) {
        throw new RuntimeException("Nesouhlasí soubor s přístupem pro Akademii.");
    }
    return $value;
}

$db = @pg_connect("host=10.239.33.12 port=5432 dbname=db_akademie user=db_akademie "
    ."sslmode=verify-full sslrootcert=/etc/polarita-akademie/postgres.crt connect_timeout=10 "
    ."password=".testPassword("pg-db_akademie"));
if (!$db) {
    throw new RuntimeException("Přihlášení Akademie k PostgreSQL selhalo.");
}
$result = pg_query($db, "SELECT current_database(),current_user,version FROM pg_stat_ssl WHERE pid=pg_backend_pid()");
if (!$result || pg_fetch_row($result) !== ["db_akademie", "db_akademie", "TLSv1.3"]) {
    throw new RuntimeException("Databáze nepotvrdila roli Akademie a TLS 1.3.");
}
pg_close($db);
$cache = new Redis();
$cache->connect("tls://10.239.33.13", 6379, 10, null, 0, 10, ["stream" => [
    "cafile" => "/etc/polarita-akademie/valkey.crt", "verify_peer" => true, "verify_peer_name" => true,
]]);
if (!$cache->auth(["akademie", testPassword("valkey-akademie")])) {
    throw new RuntimeException("Valkey odmítl aplikační účet Akademie.");
}
$key = "akademie:zkouska:".bin2hex(random_bytes(16));
if (!$cache->set($key, "test", ["nx", "ex" => 60]) || $cache->get($key) !== "test" || $cache->del($key) !== 1) {
    throw new RuntimeException("Nesouhlasí zápis nebo čtení vlastní cache Akademie.");
}
try {
    $cache->get("eshop:zkouska-opravneni");
    $error = (string)$cache->getLastError();
} catch (RedisException $e) {
    $error = $e->getMessage();
}
if (!str_contains($error, "NOPERM")) {
    throw new RuntimeException("Chybí očekávané odmítnutí čtení cizího prostoru ve Valkey.");
}
echo "PHP ověřilo TLS a vlastní účet v db_akademie, zápis a čtení cache Akademie a odmítnutí přístupu do cache e-shopu.\n";
