<?php
// Zřídí čtenáře známek v jediném cvičném kurzu. Hodnota tokenu přichází z OpenBao na stdin.
define('CLI_SCRIPT', true);
require '/opt/polarita-akademie/current/config.php';
require_once $CFG->dirroot . '/webservice/lib.php';

if (gethostname() !== 'akademie-test' || $CFG->dbname !== 'db_akademie') {
    throw new RuntimeException('Očekává se Akademie TEST.');
}
$key = stream_get_contents(STDIN, 64);
if (!preg_match('/^[0-9a-f]{32}$/D', $key)) {
    throw new RuntimeException('Neplatný přístup předaný z trezoru.');
}
$admin = get_complete_user_data('username', 'spravce');
if (!$admin || !is_siteadmin($admin) || $admin->email !== 'spravce@polarita.test') {
    throw new RuntimeException('Chybí správce Akademie TEST.');
}
\core\session\manager::set_user($admin);
$code = 'POL-TEST-AKADEMIE';
$course = $DB->get_record('course', ['idnumber' => $code, 'shortname' => $code], '*', MUST_EXIST);
$ctx = context_course::instance($course->id);
$cmid = $DB->get_field('course_modules', 'id', ['course' => $course->id, 'idnumber' => $code . '-ARCH'], MUST_EXIST);
$cm = get_coursemodule_from_id('offlinequiz', $cmid, $course->id, false, MUST_EXIST);
$uids = [];
foreach (['a' => '9000001', 'b' => '9000002'] as $variant => $number) {
    $uids[$variant] = (int)$DB->get_field('user', 'id', ['username' => 'test-akademie-' . $variant,
        'mnethostid' => $CFG->mnet_localhost_id, 'auth' => 'nologin', 'idnumber' => $number], MUST_EXIST);
}
$transaction = $DB->start_delegated_transaction();
\core\plugininfo\auth::enable_plugin('webservice', 1);
set_config('enablewebservices', 1);
$protocols = array_filter(explode(',', $CFG->webserviceprotocols ?? ''));
if (!in_array('rest', $protocols, true)) {
    $protocols[] = 'rest';
    set_config('webserviceprotocols', implode(',', $protocols));
}

$name = 'polarita-bridge-test';
$userkey = ['username' => $name, 'mnethostid' => $CFG->mnet_localhost_id];
$userfields = ['email' => $name . '@polarita.test', 'auth' => 'webservice', 'idnumber' => 'POL-TEST-COMPLIANCE'];
$user = $DB->get_record('user', $userkey);
if (!$user) {
    $id = \core\user::create_user((object)($userkey + $userfields + ['firstname' => 'Compliance',
        'lastname' => 'Bridge TEST', 'confirmed' => 1, 'lang' => 'cs']), false);
    $user = $DB->get_record('user', ['id' => $id], '*', MUST_EXIST);
}
foreach ($userfields as $field => $value) {
    if ($user->$field !== $value) {
        throw new RuntimeException('Kolize s existujícím účtem pro REST.');
    }
}
if (is_siteadmin($user) || $user->suspended || $user->deleted) {
    throw new RuntimeException('Účet čtenáře má neočekávaný stav.');
}
$rolelabel = 'Čtení známek Compliance Bridge TEST';
$role = $DB->get_record('role', ['shortname' => 'polbridgegrade']);
if ($role && ($role->name !== $rolelabel || $role->archetype !== '')) {
    throw new RuntimeException('Jméno role čtenáře už používá jiná role.');
}
$roleid = $role ? $role->id : create_role($rolelabel, 'polbridgegrade', '', '');
foreach (['webservice/rest:use', 'gradereport/user:view', 'moodle/grade:viewall', 'moodle/site:accessallgroups'] as $cap) {
    assign_capability($cap, CAP_ALLOW, $roleid, $ctx->id, true);
}
$enrol = $DB->get_record('enrol', ['courseid' => $course->id, 'enrol' => 'manual', 'status' => ENROL_INSTANCE_ENABLED], '*', MUST_EXIST);
enrol_get_plugin('manual')->enrol_user($enrol, $user->id, $roleid);

$ws = new webservice();
$short = 'polarita_bridge_znamky';
$fn = 'gradereport_user_get_grade_items';
$label = 'Známky cvičné Akademie pro Compliance Bridge';
$svc = $DB->get_record('external_services', ['shortname' => $short]);
if (!$svc) {
    $id = $ws->add_external_service((object)['name' => $label, 'shortname' => $short, 'enabled' => 1,
        'restrictedusers' => 1, 'downloadfiles' => 0, 'uploadfiles' => 0, 'requiredcapability' => 'moodle/grade:viewall']);
    $ws->add_external_function_to_service($fn, $id);
    $svc = $DB->get_record('external_services', ['id' => $id], '*', MUST_EXIST);
}
$functions = $DB->get_fieldset_select('external_services_functions', 'functionname', 'externalserviceid=?', [$svc->id]);
if ($svc->name !== $label || !$svc->enabled || !$svc->restrictedusers || $svc->downloadfiles || $svc->uploadfiles ||
        $svc->requiredcapability !== 'moodle/grade:viewall' || $functions !== [$fn]) {
    throw new RuntimeException('Rozsah služby neodpovídá čtení známek.');
}
$usercriteria = ['externalserviceid' => $svc->id, 'userid' => $user->id];
if (!$DB->record_exists('external_services_users', $usercriteria)) {
    $ws->add_ws_authorised_user((object)($usercriteria + ['iprestriction' => '127.0.0.1']));
}
$allowed = $DB->get_record('external_services_users', ['externalserviceid' => $svc->id], '*', MUST_EXIST);
if ($DB->count_records('external_services_users', ['externalserviceid' => $svc->id]) !== 1 ||
        (int)$allowed->userid !== (int)$user->id || $allowed->iprestriction !== '127.0.0.1') {
    throw new RuntimeException('Služba má neočekávaného příjemce.');
}
$token = $DB->get_record('external_tokens', ['externalserviceid' => $svc->id]);
if (!$token) {
    $generated = \core_external\util::generate_token(EXTERNAL_TOKEN_PERMANENT, $svc, $user->id, $ctx, 0, '127.0.0.1', $short);
    $DB->set_field('external_tokens', 'token', $key, ['token' => $generated, 'externalserviceid' => $svc->id]);
}
$token = $DB->get_record('external_tokens', ['externalserviceid' => $svc->id], '*', MUST_EXIST);
if ($DB->count_records('external_tokens', ['externalserviceid' => $svc->id]) !== 1 || !hash_equals($token->token, $key) || (int)$token->userid !== (int)$user->id || (int)$token->contextid !== (int)$ctx->id ||
        $token->iprestriction !== '127.0.0.1' || (int)$token->tokentype !== EXTERNAL_TOKEN_PERMANENT) {
    throw new RuntimeException('Uložený token neodpovídá trezoru, kontextu a účtu služby.');
}
$transaction->allow_commit();
echo json_encode(['course' => (int)$course->id, 'cm' => (int)$cm->id, 'a' => $uids['a'], 'b' => $uids['b']], JSON_THROW_ON_ERROR);
