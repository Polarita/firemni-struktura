<?php
// Heslo pro první přihlášení předá host na stdin. Nepřichází do argumentů procesu.
if (PHP_SAPI !== 'cli') {
    exit(1);
}
$entry = $argv[1] . '/admin/cli/install_database.php';
$password = rtrim(fgets(STDIN), "\r\n");
if ($password === '') {
    throw new RuntimeException('Chybí testovací heslo.');
}
$_SERVER['argv'] = [$entry, '--lang=en', '--adminuser=spravce', '--adminpass=' . $password,
    '--adminemail=spravce@polarita.test', '--supportemail=spravce@polarita.test',
    '--fullname=Elektro Akademie Polarity', '--shortname=Elektro Akademie', '--agree-license'];
$argv = $_SERVER['argv'];
$_SERVER['argc'] = count($argv);
require $entry;
