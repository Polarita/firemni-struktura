<?php
unset($CFG);
global $CFG;
$CFG = new stdClass();
$CFG->dbtype = 'pgsql';
$CFG->dblibrary = 'native';
$CFG->dbhost = '10.239.33.12';
$CFG->dbname = 'db_akademie';
$CFG->dbuser = 'db_akademie';
$CFG->dbpass = file_get_contents('/run/secrets/pg-db_akademie');
$CFG->prefix = 'mdl_';
$schema = PHP_SAPI === 'cli' ? getenv('POLARITA_AKADEMIE_SCHEMA') : false;
if (!$schema) {
    $schema = trim(file_get_contents('/etc/polarita-akademie/schema'));
}
if (!preg_match('/^pol_mdl_[a-f0-9]{16}$/D', $schema)) {
    throw new RuntimeException('Neplatné instalační schéma Akademie.');
}
putenv('PGSSLROOTCERT=/etc/polarita-akademie/postgres.crt');
$CFG->dboptions = ['ssl' => 'verify-full', 'dbschema' => $schema, 'dbport' => 5432, 'connecttimeout' => 15];
$CFG->wwwroot = trim(file_get_contents('/etc/polarita-akademie/url'));
$CFG->sslproxy = true;
$CFG->dataroot = '/var/lib/polarita-akademie/' . $schema;
$CFG->directorypermissions = 0700;
$CFG->sessioncookie = 'PolAkademie';
$CFG->cookiesecure = true;
$CFG->forcelogin = true;
$CFG->noemailever = true;
$CFG->disableupdateautodeploy = true;
