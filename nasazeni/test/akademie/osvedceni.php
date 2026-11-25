<?php
use mod_customcert\service\element_factory;
use mod_customcert\service\element_layout;
use mod_customcert\service\element_repository;
use mod_customcert\service\page_repository;
use mod_customcert\service\pdf_generation_service;
use mod_customcert\service\persistence_helper;
use mod_customcert\service\template_repository;

function vzor_osvedceni($course, $quiz, $code) {
    global $DB, $CFG;
    if (empty($CFG->enableavailability)) {
        throw new RuntimeException('Podmíněný přístup ke cvičnému osvědčení není zapnutý.');
    }
    $grade = $DB->get_field('grade_items', 'id', [
        'courseid' => $course->id, 'itemtype' => 'mod', 'itemmodule' => 'offlinequiz',
        'iteminstance' => $quiz->id, 'itemnumber' => 0,
    ], MUST_EXIST);
    $condition = ['op' => '&', 'c' => [['type' => 'grade', 'id' => (int)$grade, 'min' => 100]], 'showc' => [true]];
    $transaction = $DB->start_delegated_transaction();
    $cm = aktivita($course, 'customcert', "$code-OSVEDCENI", 'Cvičné osvědčení Akademie', [
        'availabilityconditionsjson' => json_encode($condition, JSON_THROW_ON_ERROR),
        'emailothers' => '', 'emailstudents' => 0, 'emailteachers' => 0, 'issueautomatically' => 0,
    ]);
    if (json_decode($cm->availability ?? 'null', true) != $condition) {
        throw new RuntimeException('Osvědčení nemá podmínku plného počtu bodů ze cvičné zkoušky.');
    }
    $cert = $DB->get_record('customcert', ['id' => $cm->instance], '*', MUST_EXIST);
    $template = \mod_customcert\template::from_record((new template_repository())->get_by_id_or_fail((int)$cert->templateid));
    $pages = (new page_repository())->list_by_template((int)$cert->templateid);
    $page = reset($pages);
    $factory = element_factory::build_with_defaults();
    $elements = new element_repository($factory);
    $rows = [
        ['Název', 'text', 'Cvičné osvědčení Akademie', 28, 22],
        ['Označení vzoru', 'text', 'VZOR TEST', 50, 18],
        ['Jméno účastníka', 'studentname', '', 72, 16],
        ['Kurz', 'text', 'Kurz: vyplnění odpovědního listu', 94, 13],
        ['Účel', 'text', 'Doklad k ověření tisku a zpracování cvičné zkoušky.', 112, 11],
    ];
    foreach ($rows as [$name, $type, $text, $y, $size]) {
        $record = (object)['pageid' => $page->id, 'name' => $name, 'element' => $type,
            'posx' => 20, 'posy' => $y, 'refpoint' => 0, 'alignment' => 'L'];
        if ($DB->record_exists('customcert_elements', ['pageid' => $page->id, 'name' => $name, 'element' => $type])) {
            continue;
        }
        $form = (object)['text' => $text, 'font' => 'freesans', 'fontsize' => $size, 'colour' => '202020', 'width' => 165];
        $record->data = persistence_helper::to_json_data($factory->create($type, $record), $form);
        $elements->create($factory->create($type, $record), element_layout::from_record($record));
    }
    $transaction->allow_commit();
    $person = $DB->get_record('user', ['username' => 'test-akademie-a', 'auth' => 'nologin',
        'email' => 'test-akademie-a@polarita.test', 'mnethostid' => $CFG->mnet_localhost_id], '*', MUST_EXIST);
    $pdf = pdf_generation_service::create()->generate_pdf($template, true, (int)$person->id, true);
    if (!is_string($pdf) || !str_starts_with($pdf, '%PDF-')) {
        throw new RuntimeException('Custom Certificate nevytvořil náhled PDF.');
    }
    $temp = tempnam('/var/lib/polarita-vzory', 'osvedceni-');
    try {
        if (file_put_contents($temp, $pdf) !== strlen($pdf) || !rename($temp, '/var/lib/polarita-vzory/osvedceni.pdf')) {
            throw new RuntimeException('Soubor s cvičným osvědčením nelze uložit.');
        }
    } finally {
        if (is_file($temp)) {
            unlink($temp);
        }
    }
}
