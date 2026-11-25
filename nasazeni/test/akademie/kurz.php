<?php
// Vytvoří soukromý cvičný kurz a tisknutelné archy přímo v Offline Quiz.
define('CLI_SCRIPT', true);
require '/opt/polarita-akademie/current/config.php';
require_once $CFG->dirroot . '/course/lib.php';
require_once $CFG->dirroot . '/group/lib.php';
require_once $CFG->dirroot . '/mod/offlinequiz/lib.php';
require_once $CFG->dirroot . '/mod/offlinequiz/locallib.php';
require_once $CFG->dirroot . '/mod/offlinequiz/pdflib.php';
require_once $CFG->libdir . '/resourcelib.php';

function aktivita($course, $type, $key, $name, $options = []) {
    global $DB;
    $existing = $DB->get_record('course_modules', ['course' => $course->id, 'idnumber' => $key]);
    if ($existing) {
        return get_coursemodule_from_id($type, $existing->id, $course->id, false, MUST_EXIST);
    }
    $data = (object)($options + [
        'course' => $course->id, 'section' => 0, 'visible' => 1, 'modulename' => $type,
        'cmidnumber' => $key, 'name' => $name,
        'introeditor' => ['text' => '', 'format' => FORMAT_HTML, 'itemid' => 0],
    ]);
    $new = create_module($data);
    return get_coursemodule_from_id($type, $new->coursemodule, $course->id, false, MUST_EXIST);
}

function otazka($category, $key, $title, $answers, $correct) {
    global $DB;
    $entry = $DB->get_record('question_bank_entries', ['questioncategoryid' => $category->id, 'idnumber' => $key]);
    if ($entry) {
        $versions = $DB->get_records('question_versions', ['questionbankentryid' => $entry->id, 'status' => 'ready'], 'version DESC', '*', 0, 1);
        if (!$versions) {
            throw new RuntimeException('Chybí dostupná verze otázky ' . $key);
        }
        return (int)reset($versions)->questionid;
    }
    $editor = fn($text) => ['text' => $text, 'format' => FORMAT_HTML];
    $empty = $editor('');
    $form = (object)[
        'category' => (string)$category->id, 'name' => $title, 'idnumber' => $key, 'defaultmark' => 1,
        'questiontext' => $editor($title), 'generalfeedback' => $empty, 'single' => 1,
        'shuffleanswers' => 0, 'answernumbering' => 'abc', 'answer' => array_map($editor, $answers),
        'feedback' => array_fill(0, count($answers), $empty), 'fraction' => array_fill(0, count($answers), 0),
        'correctfeedback' => $empty, 'partiallycorrectfeedback' => $empty, 'incorrectfeedback' => $empty,
    ];
    $form->fraction[$correct] = 1;
    return (int)question_bank::get_qtype('multichoice')->save_question((object)['qtype' => 'multichoice'], $form)->id;
}

if (gethostname() !== 'akademie-test' || $CFG->dbname !== 'db_akademie' || !preg_match('~^https://[a-z0-9.-]+\.ts\.net:8451$~D', $CFG->wwwroot)) {
    throw new RuntimeException('Cvičný kurz vyžaduje TEST Akademie.');
}
$admin = get_complete_user_data('username', 'spravce');
if (!$admin || !is_siteadmin($admin) || $admin->email !== 'spravce@polarita.test') {
    throw new RuntimeException('Chybí testovací správce.');
}
\core\session\manager::set_user($admin);
$code = 'POL-TEST-AKADEMIE';
$transaction = $DB->start_delegated_transaction();
$course = $DB->get_record('course', ['idnumber' => $code]);
if (!$course) {
    $course = create_course((object)[
        'category' => core_course_category::get_default()->id, 'idnumber' => $code, 'shortname' => $code,
        'fullname' => 'Cvičná zkouška Akademie', 'summary' => 'Nácvik vyplnění a vyhodnocení papírového listu s fiktivními účastníky.',
        'summaryformat' => FORMAT_PLAIN, 'format' => 'topics', 'groupmode' => SEPARATEGROUPS,
    ]);
}
if ($course->shortname !== $code) {
    throw new RuntimeException('Identifikátor kurzu již používá jiný kurz.');
}
$context = context_course::instance($course->id);
$PAGE->set_course($course);
$manual = $DB->get_record('enrol', ['courseid' => $course->id, 'enrol' => 'manual', 'status' => ENROL_INSTANCE_ENABLED], '*', MUST_EXIST);
$plugin = enrol_get_plugin('manual');
$teacher = $DB->get_field('role', 'id', ['shortname' => 'editingteacher'], MUST_EXIST);
$student = $DB->get_field('role', 'id', ['shortname' => 'student'], MUST_EXIST);
$plugin->enrol_user($manual, $admin->id, $teacher);
foreach (['A' => '9000001', 'B' => '9000002'] as $label => $number) {
    $key = "$code-$label";
    $gid = groups_get_group_by_idnumber($course->id, $key);
    if (!$gid) {
        $gid = groups_create_group((object)['courseid' => $course->id, 'idnumber' => $key,
            'name' => "Cvičná skupina $label", 'participation' => 1]);
    } else {
        $gid = $gid->id;
    }
    $username = 'test-akademie-' . strtolower($label);
    $email = "$username@polarita.test";
    $user = $DB->get_record('user', ['mnethostid' => $CFG->mnet_localhost_id, 'username' => $username]);
    if (!$user) {
        $uid = \core\user::create_user((object)['username' => $username, 'mnethostid' => $CFG->mnet_localhost_id,
            'firstname' => 'Účastník', 'lastname' => "TEST $label", 'email' => $email, 'auth' => 'nologin',
            'confirmed' => 1, 'idnumber' => $number, 'lang' => 'cs'], false);
    } else {
        if ($user->deleted || $user->auth !== 'nologin' || $user->email !== $email || $user->idnumber !== $number) {
            throw new RuntimeException('Kolize se stávajícím účtem ' . $username);
        }
        $uid = $user->id;
    }
    $plugin->enrol_user($manual, $uid, $student);
    groups_add_member($gid, $uid);
    if (!is_enrolled($context, $uid, '', true) || !groups_is_member($gid, $uid)) {
        throw new RuntimeException('Chybí aktivní zápis do cvičné skupiny ' . $label);
    }
}
aktivita($course, 'page', "$code-NAVOD", 'Jak vyplnit cvičný odpovědní list', [
    'display' => RESOURCELIB_DISPLAY_AUTO, 'printintro' => 0, 'printlastmodified' => 0, 'contentformat' => FORMAT_HTML,
    'content' => '<p>Zkontrolujte písmeno varianty a identifikátor na svém cvičném listu. U každé otázky označte právě jednu odpověď. Po odevzdání listu školitel načte jeho sken a porovná výsledek s klíčem.</p>',
]);
$bank = aktivita($course, 'qbank', "$code-BANKA", 'Otázky pro cvičnou zkoušku', ['visible' => 0]);
$category = question_get_default_category(context_module::instance($bank->id)->id, true);
$first = otazka($category, "$code-01", 'Co zkontrolujete před vyplněním listu?', ['Barvu složky', 'Variantu a identifikátor', 'Číslo tiskárny'], 1);
$second = otazka($category, "$code-02", 'Kolik možností označíte u otázky s jedinou správnou odpovědí?', ['Jednu', 'Dvě', 'Všechny'], 0);
$cm = aktivita($course, 'offlinequiz', "$code-ARCH", 'TEST – vyplnění odpovědního listu', [
    'groupmode' => SEPARATEGROUPS, 'numgroups' => 2, 'pdfintro' => '', 'timeopen' => 0, 'timeclose' => 0,
    'time' => 0, 'decimalpoints' => 2, 'questionsperpage' => 0, 'shufflequestions' => 0, 'shuffleanswers' => 0,
    'papergray' => 670, 'fontsize' => 10, 'fileformat' => 0, 'pdffont' => 'freesans', 'participantsusage' => 1,
]);
$quiz = $DB->get_record('offlinequiz', ['id' => $cm->instance], '*', MUST_EXIST);
$quiz->cmid = $cm->id;
$modulecontext = context_module::instance($cm->id);
foreach ([1 => [$first, $second], 2 => [$second, $first]] as $variant => $questions) {
    $group = offlinequiz_get_group($quiz, $variant);
    $quiz->groupid = $group->id;
    $existing = array_map('intval', offlinequiz_get_group_question_ids($quiz, $group->id));
    if (!$existing && !$quiz->docscreated) {
        foreach ($questions as $qid) {
            if (!offlinequiz_add_offlinequiz_question($qid, $quiz)) {
                throw new RuntimeException('Otázku nelze přiřadit do varianty.');
            }
        }
        offlinequiz_update_sumgrades($quiz, $group->id);
    }
    if (array_map('intval', offlinequiz_get_group_question_ids($quiz, $group->id)) !== $questions) {
        throw new RuntimeException('Nesouhlasí obsah nebo pořadí otázek ve variantě ' . $variant);
    }
}
$transaction->allow_commit();

$transaction = $DB->start_delegated_transaction();
foreach ([1, 2] as $variant) {
    $group = offlinequiz_get_group($quiz, $variant);
    $quiz->groupid = $group->id;
    if (!$quiz->docscreated) {
        $usage = offlinequiz_get_group_template_usage($quiz, $group, $modulecontext);
        $group->questionfilename = offlinequiz_create_pdf_question($usage, $quiz, $group, $course->id, $modulecontext)->get_filename();
        $group->answerfilename = offlinequiz_create_pdf_answer(offlinequiz_get_maxanswers($quiz, [$group]), $usage, $quiz, $group, $course->id, $modulecontext)->get_filename();
        $group->correctionfilename = offlinequiz_create_pdf_question($usage, $quiz, $group, $course->id, $modulecontext, true)->get_filename();
        $DB->update_record('offlinequiz_groups', $group);
    }
    foreach (['questionfilename', 'answerfilename', 'correctionfilename'] as $field) {
        $file = get_file_storage()->get_file($modulecontext->id, 'mod_offlinequiz', 'pdfs', 0, '/', $group->$field);
        if (!$file || !str_starts_with($file->get_content(), '%PDF-')) {
            throw new RuntimeException('V úložišti Moodle chybí PDF ' . $field);
        }
    }
}
if (!$quiz->docscreated) {
    $DB->set_field('offlinequiz', 'id_digits', get_config('offlinequiz', 'ID_digits'), ['id' => $quiz->id]);
    $DB->set_field('offlinequiz', 'docscreated', 1, ['id' => $quiz->id]);
    \mod_offlinequiz\event\docs_created::create(['context' => $modulecontext,
        'other' => ['offlinequizid' => $quiz->id, 'reportname' => 'createpdfs', 'doctype' => 'PDF']])->trigger();
}
$transaction->allow_commit();
echo "Kurz $code: dva zapsaní účastníci, dvě různé varianty a šest PDF (zadání, arch a klíč).\n";
require __DIR__ . '/osvedceni.php';
vzor_osvedceni($course, $quiz, $code);
