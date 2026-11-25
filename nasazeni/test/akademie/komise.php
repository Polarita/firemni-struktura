<?php
// Volá vydani.php po ověření obou účastníků a jejich přístupu k osvědčení.
defined('MOODLE_INTERNAL') || die();
require_once $CFG->libdir . '/pdflib.php';
$data = json_decode(stream_get_contents(STDIN, 4096), true, 16, JSON_THROW_ON_ERROR);
if ($data['course'] !== (int)$course->id || $data['cm'] !== (int)$quizcm->id ||
        !preg_match('/^[0-9a-f]{64}$/D', $data['osvedceni'])) {
    throw new RuntimeException('Podklady komise neodpovídají cvičnému kurzu.');
}
foreach (['a' => 100, 'b' => 50] as $group => $expected) {
    $uid = (int)$DB->get_field('user', 'id', ['username' => 'test-akademie-' . $group,
        'auth' => 'nologin', 'mnethostid' => $CFG->mnet_localhost_id], MUST_EXIST);
    if ($data['znamky'][$group]['userid'] !== $uid || $data['znamky'][$group]['procent'] !== $expected) {
        throw new RuntimeException('Známka z REST nebo příjemce neodpovídá cvičné zkoušce.');
    }
}
$issue = $DB->get_record('customcert_issues', $criteria, '*', MUST_EXIST);
$result = $DB->get_record('offlinequiz_results', ['offlinequizid' => $quizcm->instance,
    'userid' => $recipient->id, 'status' => 'complete'], '*', MUST_EXIST);
if (!$result->timefinish || (int)$result->timefinish > (int)$issue->timecreated) {
    throw new RuntimeException('Vydání osvědčení musí následovat po vyhodnocení zkoušky.');
}
$exam = (new DateTimeImmutable('@' . $result->timefinish))->setTimezone(new DateTimeZone('Europe/Prague'));
$end = $exam->modify('+3 years');
if ($exam->format('m') !== $end->format('m')) {
    $end = $end->modify('-1 day');
}
$source = hash('sha256', $CFG->wwwroot . ':' . $issue->id . ':' . $issue->code);
$record = ['rezim' => 'TEST', 'druh' => 'elektrotechnik', 'zkouska' => (int)$result->id,
    'vydani' => $source, 'osvedceni_sha256' => $data['osvedceni'], 'osoba' => $recipient->username,
    'procent' => $data['znamky']['a']['procent'], 'provedeno' => $exam->format(DATE_ATOM),
    'platnost_do' => $end->format('Y-m-d'), 'komise' => ['TEST-PREDS-1001', 'TEST-CLEN-02', 'TEST-CLEN-03']];
$pdf = new pdf();
$pdf->setPrintHeader(false);
$pdf->setPrintFooter(false);
$pdf->SetMargins(20, 21, 20);
$pdf->SetTitle('Protokol cvičné zkoušky elektrotechnika');
$pdf->AddPage();
$pdf->SetFont('freesans', '', 11);
$pdf->Write(6, "Polarita s.r.o.   /   Akademie   /   VZOR TEST");
$pdf->Ln(14);
$pdf->SetFont('freesans', '', 20);
$pdf->MultiCell(0, 10, "Protokol cvičné zkoušky elektrotechnika", 0, 'L');
$pdf->Ln(5);
$pdf->SetFont('freesans', '', 11);
foreach (['Účastník' => 'TEST A', 'Kurz' => $course->shortname, 'Datum zkoušky' => $exam->format('d.m.Y'),
        'Výsledek Offline Quiz' => $record['procent'] . ' %', 'Konec cvičné platnosti' => $end->format('d.m.Y'),
        'Předseda cvičné komise' => $record['komise'][0], 'Další členové cvičné komise' => implode(', ', array_slice($record['komise'], 1))]
        as $label => $value) {
    $pdf->MultiCell(0, 8, "$label: $value", 0, 'L');
}
$pdf->Ln(5);
$pdf->MultiCell(0, 7, 'SHA-256 vydaného osvědčení', 0, 'L');
$pdf->SetFont('freesans', '', 9);
$pdf->MultiCell(0, 6, $record['osvedceni_sha256'], 0, 'L');
$pdf->Ln(6);
$pdf->SetFont('freesans', '', 10);
$pdf->MultiCell(0, 7, 'Instalační zkouška s fiktivním účastníkem a tříčlennou komisí. Dokument je určen k ověření místní testovací pečeti.', 0, 'L');
echo json_encode(['udaje' => $record, 'pdf' => base64_encode($pdf->Output('', 'S'))], JSON_THROW_ON_ERROR);
