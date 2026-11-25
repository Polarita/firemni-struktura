<?php
// Připojí místní účet správce k ověřené identitě v testovacím realmu.
define('CLI_SCRIPT', true);
require '/opt/polarita-akademie/current/config.php';

use core\oauth2\api;
use core\oauth2\issuer;
use core\oauth2\user_field_mapping;
use core\session\manager;
use auth_oauth2\api as logins;

[$script, $host, $subject] = $argv;
$root = 'https://' . $host;
$base = $root . '/identita/realms/polarita';
if ($CFG->wwwroot !== $root . ':8451' || !preg_match('/^[a-z0-9.-]+\.ts\.net$/D', $host)
        || gethostbynamel($host) !== ['10.239.32.13']) {
    throw new RuntimeException('Nesouhlasí umístění Akademie nebo vstupu identity.');
}
$admin = get_complete_user_data('username', 'spravce');
if (!$admin || !is_siteadmin($admin) || $admin->email !== 'spravce@polarita.test' || $admin->suspended) {
    throw new RuntimeException('Moodle nepotvrdil spravovaný místní účet.');
}
manager::set_user($admin);

$path = '/run/secrets/akademie-oidc_secret';
$key = file_get_contents($path);
if (!$key || !preg_match('/^[A-Za-z0-9_-]{48,100}$/D', $key) || (fileperms($path) & 0777) !== 0400) {
    throw new RuntimeException('Chybí klientský údaj z OpenBao.');
}
$transaction = $DB->start_delegated_transaction();
$blocked = preg_split('/\R/', $CFG->curlsecurityblockedhosts);
$networks = json_decode(stream_get_contents(STDIN), true, flags: JSON_THROW_ON_ERROR);
$index = array_search('10.0.0.0/8', $blocked, true);
if ($index !== false) {
    array_splice($blocked, $index, 1, $networks);
    set_config('curlsecurityblockedhosts', implode("\n", $blocked));
}
$guard = new core\files\curl_security_helper();
if ($guard->url_is_blocked($base . '/.well-known/openid-configuration')
        || !$guard->url_is_blocked('https://10.239.32.11/')
        || !$guard->url_is_blocked('https://10.239.33.12/')) {
    throw new RuntimeException('Pravidla odchozího HTTPS nepotvrdila vyhrazený vstup identity.');
}
$http = new curl();
$metadata = json_decode($http->get($base . '/.well-known/openid-configuration'), true, flags: JSON_THROW_ON_ERROR);
$paths = ['authorization' => 'auth', 'token' => 'token', 'userinfo' => 'userinfo'];
if ($http->get_errno() || ($metadata['issuer'] ?? '') !== $base) {
    throw new RuntimeException('Moodle nepotvrdil pravost vydavatele.');
}
foreach ($paths as $name => $path) {
    if (($metadata[$name . '_endpoint'] ?? '') !== "$base/protocol/openid-connect/$path") {
        throw new RuntimeException('Nesouhlasí cílová adresa přihlášení.');
    }
}

$data = (object) ['name' => 'Ředitelství Polarity', 'loginpagename' => 'Ředitelství Polarity',
    'baseurl' => $base, 'servicetype' => 'custom', 'clientid' => 'moodle', 'clientsecret' => $key,
    'alloweddomains' => 'polarita.test', 'requireconfirmation' => true, 'enabled' => true,
    'showonloginpage' => issuer::LOGINONLY, 'loginscopes' => 'openid profile email'];
$existing = issuer::get_records(['clientid' => 'moodle']);
if (!$existing) {
    $issuer = api::create_issuer($data);
} else {
    $issuer = reset($existing);
    if (count($existing) !== 1 || $issuer->get('baseurl') !== $base) {
        throw new RuntimeException('ID klienta Moodle používá jiný vydavatel.');
    }
    foreach ($data as $field => $value) {
        $issuer->set($field, $value);
    }
    $issuer->update();
}
foreach ($paths as $name => $path) {
    if ((string)$issuer->get_endpoint_url($name) !== $metadata[$name . '_endpoint']) {
        throw new RuntimeException('Uložený koncový bod se neshoduje s metadaty.');
    }
}

$issuerid = $issuer->get('id');
$mapping = user_field_mapping::get_records(['issuerid' => $issuerid, 'internalfield' => 'username']);
if (!$mapping) {
    api::create_user_field_mapping((object)['issuerid' => $issuerid, 'internalfield' => 'username', 'externalfield' => 'sub']);
} elseif (count($mapping) !== 1 || reset($mapping)->get('externalfield') !== 'sub') {
    throw new RuntimeException('Uživatelské jméno poskytovatele už používá jiné mapování.');
}
$linked = logins::match_username_to_user($subject, $issuer);
if (!$linked) {
    $linked = logins::link_login(['username' => $subject, 'email' => $admin->email], $issuer, $admin->id);
}
if ((int)$linked->get('userid') !== (int)$admin->id || $linked->get('confirmtoken')) {
    throw new RuntimeException('Vazba účtu správce na subjekt Keycloaku nesouhlasí.');
}
\core\plugininfo\auth::enable_plugin('oauth2', 1);
$transaction->allow_commit();
echo "Moodle ověřil přes HTTPS poskytovatele a propojil účet spravce s identifikátorem z testovacího realmu.\n";
