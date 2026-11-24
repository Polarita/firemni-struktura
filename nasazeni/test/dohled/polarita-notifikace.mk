# Dvě nezávislé cesty místních testovacích událostí. Oba transporty přijímají pouze na loopbacku.
for plugin, parameter, rule in (
    ("polarita_smtp","2ee2acd2-0df3-4946-9533-0246d455c332","d59714eb-fbe9-48f8-9042-702582193e76"),
    ("polarita_telegram","8ebb7e96-86b1-442d-bb77-6e843de8e134","efcc9ff8-99d4-4afb-90be-e777302fe763"),
):
    notification_parameter.setdefault(plugin,{})[parameter] = {
        "general":{"description":"Doručení v TEST","comment":"","docu_url":""},
        "parameter_properties":{},
    }
    notification_rules.append({
        "rule_id":rule,"allow_disable":False,"contact_all":False,"contact_all_with_email":False,
        "contact_object":False,"contact_users":["cmkadmin"],"description":"TEST "+plugin,
        "disabled":False,"notify_plugin":(plugin,parameter),"match_hosts":["polarita-hq"],
        "match_service_event":["rc","wc","uc","?c","cr"],
        "match_host_event":["rd","ud","?d","dr"],
    })
