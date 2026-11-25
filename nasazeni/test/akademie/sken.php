<?php
define('CLI_SCRIPT', true);
require '/opt/polarita-akademie/current/config.php';
require_once $CFG->dirroot . '/mod/offlinequiz/lib.php';

[$script, $action, $label] = $argv;
if (gethostname() !== 'akademie-test' || $CFG->dbname !== 'db_akademie' ||
        !in_array($action, ['arch', 'odesli', 'over'], true) || !in_array($label, ['A', 'B'], true)) {
    throw new RuntimeException('Neplatná zkouška skenování Akademie.');
}
$admin = get_complete_user_data('username', 'spravce');
if (!$admin || !is_siteadmin($admin) || $admin->email !== 'spravce@polarita.test') {
    throw new RuntimeException('Chybí testovací správce.');
}
\core\session\manager::set_user($admin);
$course = $DB->get_record('course', ['shortname' => 'POL-TEST-AKADEMIE', 'idnumber' => 'POL-TEST-AKADEMIE'], '*', MUST_EXIST);
$cm = $DB->get_record('course_modules', ['course' => $course->id, 'idnumber' => 'POL-TEST-AKADEMIE-ARCH'], '*', MUST_EXIST);
$quiz = $DB->get_record('offlinequiz', ['course' => $course->id, 'id' => $cm->instance, 'docscreated' => 1], '*', MUST_EXIST);
$variant = $label === 'A' ? 1 : 2;
$expected = $label === 'A' ? 100 : 50;
$person = $DB->get_record('user', ['mnethostid' => $CFG->mnet_localhost_id, 'auth' => 'nologin',
    'username' => 'test-akademie-' . strtolower($label), 'idnumber' => '900000' . $variant], '*', MUST_EXIST);
$group = $DB->get_record('offlinequiz_groups', ['offlinequizid' => $quiz->id, 'groupnumber' => $variant], '*', MUST_EXIST);
$context = context_module::instance($cm->id);
$fs = get_file_storage();
$sheet = $fs->get_file($context->id, 'mod_offlinequiz', 'pdfs', 0, '/', $group->answerfilename);
if (!$sheet || get_config('offlinequiz', 'useridentification') !== '[7]=idnumber') {
    throw new RuntimeException('Nesouhlasí arch nebo identifikace účastníků.');
}
if ($action === 'arch') {
    echo $sheet->get_content();
    exit;
}
if ($action === 'odesli') {
    $png = stream_get_contents(STDIN, 8000001);
    if (!str_starts_with($png, "\x89PNG\r\n\x1a\n") || strlen($png) > 8000000) {
        throw new RuntimeException('Chybí vyplněný obraz archu.');
    }
    $name = 'TEST-' . $label . '-' . substr(hash('sha256', $png), 0, 20) . '.png';
    $criteria = ['offlinequizid' => $quiz->id, 'importuserid' => $admin->id, 'filename' => $name];
    $job = $DB->get_record('offlinequiz_queue', $criteria);
    if (!$job) {
        $transaction = $DB->start_delegated_transaction();
        $id = $DB->insert_record('offlinequiz_queue', (object)($criteria + ['timecreated' => time(), 'timestart' => 0,
            'timefinish' => 0, 'status' => 'uploading']));
        make_upload_directory("offlinequiz/import/$id");
        $fs->create_file_from_string(['contextid' => $context->id, 'component' => 'mod_offlinequiz', 'filearea' => 'queue',
            'itemid' => $id, 'filepath' => '/', 'filename' => $name], $png);
        $task = \offlinequiz_rimport\task\adhoc\extract_files::instance($id);
        $task->set_next_run_time(time());
        \core\task\manager::queue_adhoc_task($task, true);
        $transaction->allow_commit();
    } else {
        $id = $job->id;
    }
    echo (int)$id;
    exit;
}
$id = filter_var(trim(stream_get_contents(STDIN)), FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);
$job = $DB->get_record('offlinequiz_queue', ['id' => $id, 'offlinequizid' => $quiz->id, 'importuserid' => $admin->id], '*', MUST_EXIST);
if (!preg_match('/^TEST-' . $label . '-[0-9a-f]{20}\.png$/D', $job->filename)) {
    throw new RuntimeException('Zkouška nemá odpovídající úlohu importu.');
}
$entry = $DB->get_record('offlinequiz_queue_data', ['queueid' => $job->id]);
$page = $entry ? $DB->get_record('offlinequiz_scanned_pages', ['queuedataid' => $entry->id, 'offlinequizid' => $quiz->id]) : false;
foreach ([$job, $entry, $page] as $record) {
    if ($record && $record->status === 'error') {
        $error = preg_replace('/[^a-zA-Z0-9_]/', '', (string)$record->error);
        throw new RuntimeException("Offline Quiz odmítl arch $label ($error).");
    }
}
if (!$page || !$page->resultid) {
    exit(75);
}
$result = $DB->get_record('offlinequiz_results', ['id' => $page->resultid, 'offlinequizid' => $quiz->id], '*', MUST_EXIST);
if ($result->status !== 'complete' || (int)$result->userid !== (int)$person->id ||
        (int)$result->offlinegroupid !== (int)$group->id || (float)$result->sumgrades !== $expected / 50.0) {
    throw new RuntimeException("Nesouhlasí rozpoznaná osoba, varianta nebo počet bodů na archu $label.");
}
$grade = $DB->get_field_sql('SELECT g.finalgrade FROM {grade_grades} g JOIN {grade_items} i ON i.id=g.itemid
    WHERE g.userid=? AND i.courseid=? AND i.itemtype=? AND i.itemmodule=? AND i.iteminstance=? AND i.itemnumber=0',
    [$person->id, $course->id, 'mod', 'offlinequiz', $quiz->id]);
if ($grade === false || $grade === null) {
    exit(75);
}
$cert = $DB->get_record('course_modules', ['course' => $course->id, 'idnumber' => 'POL-TEST-AKADEMIE-OSVEDCENI'], '*', MUST_EXIST);
$available = get_fast_modinfo($course, $person->id)->get_cm($cert->id)->available;
if ((float)$grade !== (float)$expected || (bool)$available !== ($expected === 100)) {
    throw new RuntimeException("Známka nebo dostupnost osvědčení po vyhodnocení archu $label nesouhlasí.");
}
echo "Offline Quiz přečetl arch $label, přiřadil jej účastníkovi a uložil $expected %. Přístup k osvědčení odpovídá výsledku.\n";
