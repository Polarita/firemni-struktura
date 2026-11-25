<?php
// SPDX-License-Identifier: GPL-3.0-or-later
defined('MOODLE_INTERNAL') || die();
class cachestore_polaritavalkey_addinstance_form extends cachestore_addinstance_form {
    protected function configuration_definition() {
        $this->_form->addElement('static', 'connection', '', get_string('connection', 'cachestore_polaritavalkey'));
    }
}
