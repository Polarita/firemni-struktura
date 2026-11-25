<?php
// Vydání cvičného osvědčení jen po vyhodnocení skutečných archů Offline Quiz.
define('CLI_SCRIPT', true);
require '/opt/polarita-akademie/current/config.php';

use mod_customcert\service\certificate_issue_service;
use mod_customcert\service\element_factory;
use mod_customcert\service\element_layout;
use mod_customcert\service\element_repository;
use mod_customcert\service\page_repository;
use mod_customcert\service\pdf_generation_service;
use mod_customcert\service\persistence_helper;
use mod_customcert\service\template_repository;

$action = $argv[1] ?? '';
if (gethostname() !== 'akademie-test' || $CFG->dbname !== 'db_akademie' || !in_array($action, ['pdf', 'over'], true)) {
    throw new RuntimeException('Vydání vzoru vyžaduje testovací Akademii.');
}
$admin = get_complete_user_data('username', 'spravce');
if (!$admin || !is_siteadmin($admin) || $admin->email !== 'spravce@polarita.test') {
    throw new RuntimeException('Chybí správce TEST.');
}
\core\session\manager::set_user($admin);
$course = $DB->get_record('course', ['idnumber' => 'POL-TEST-AKADEMIE', 'shortname' => 'POL-TEST-AKADEMIE'], '*', MUST_EXIST);
$PAGE->set_course($course);
$cm = $DB->get_record('course_modules', ['course' => $course->id, 'idnumber' => 'POL-TEST-AKADEMIE-OSVEDCENI'], '*', MUST_EXIST);
$cert = $DB->get_record('customcert', ['id' => $cm->instance, 'course' => $course->id], '*', MUST_EXIST);
$quizcm = $DB->get_record('course_modules', ['course' => $course->id, 'idnumber' => 'POL-TEST-AKADEMIE-ARCH'], '*', MUST_EXIST);
$context = context_module::instance($cm->id);
foreach (['b' => 1, 'a' => 2] as $variant => $points) {
    $username = 'test-akademie-' . $variant;
    $person = get_complete_user_data('username', $username);
    if (!$person || $person->deleted || $person->suspended || $person->auth !== 'nologin' || $person->email !== "$username@polarita.test") {
        throw new RuntimeException('Cvičný účet se liší od účastníka zkoušky.');
    }
    $result = $DB->get_record('offlinequiz_results', ['offlinequizid' => $quizcm->instance, 'userid' => $person->id], '*', MUST_EXIST);
    $available = get_fast_modinfo($course, $person->id)->get_cm($cm->id)->available;
    if ($result->status !== 'complete' || (float)$result->sumgrades !== (float)$points || (bool)$available !== ($variant === 'a')) {
        throw new RuntimeException('Výsledek zkoušky nebo podmínka vydání se změnily.');
    }
    if ($variant === 'b' && $DB->record_exists('customcert_issues', ['customcertid' => $cert->id, 'userid' => $person->id])) {
        throw new RuntimeException('Účastník s polovičním výsledkem má vystavené osvědčení.');
    }
}
$recipient = get_complete_user_data('username', 'test-akademie-a');
$criteria = ['customcertid' => $cert->id, 'userid' => $recipient->id];
if ($action === 'over') {
    $url = trim(stream_get_contents(STDIN, 4096));
    $endpoint = $CFG->wwwroot . '/mod/customcert/verify_certificate.php?';
    if (!str_starts_with($url, $endpoint) || str_contains($url, '#')) {
        throw new RuntimeException('QR kód nevede k ověření osvědčení Akademie.');
    }
    parse_str(substr($url, strlen($endpoint)), $args);
    $issue = $DB->get_record('customcert_issues', $criteria, '*', MUST_EXIST);
    if (($args['qrcode'] ?? '') !== '1' || !hash_equals($issue->code, $args['code'] ?? '') ||
            (isset($args['contextid']) && (string)$context->id !== $args['contextid'])) {
        throw new RuntimeException('QR kód neodpovídá vydanému osvědčení účastníka A.');
    }
    echo "QR z vytištěného PDF odpovídá vydanému osvědčení v Moodle. Účastník B žádné vydané osvědčení nemá.\n";
    exit;
}
$template = \mod_customcert\template::from_record((new template_repository())->get_by_id_or_fail((int)$cert->templateid));
$pages = (new page_repository())->list_by_template((int)$cert->templateid);
$page = reset($pages);
$transaction = $DB->start_delegated_transaction();
$name = 'Ověření osvědčení';
if (!$DB->record_exists('customcert_elements', ['pageid' => $page->id, 'name' => $name, 'element' => 'qrcode'])) {
    $factory = element_factory::build_with_defaults();
    $record = (object)['pageid' => $page->id, 'name' => $name, 'element' => 'qrcode', 'posx' => 20, 'posy' => 134,
        'alignment' => 'L', 'refpoint' => 0];
    $record->data = persistence_helper::to_json_data($factory->create('qrcode', $record), (object)['width' => 32, 'height' => 32]);
    (new element_repository($factory))->create($factory->create('qrcode', $record), element_layout::from_record($record));
}
\core\session\manager::set_user($recipient);
require_capability('mod/customcert:receiveissue', $context);
if (!$DB->record_exists('customcert_issues', $criteria)) {
    certificate_issue_service::create()->issue_certificate((int)$cert->id, (int)$recipient->id);
}
$transaction->allow_commit();
$pdf = pdf_generation_service::create()->generate_pdf($template, false, (int)$recipient->id, true);
if (!is_string($pdf) || !str_starts_with($pdf, '%PDF-')) {
    throw new RuntimeException('Custom Certificate nevygeneroval vydaný dokument.');
}
echo $pdf;
