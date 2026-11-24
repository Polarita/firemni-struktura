plugin = "polarita_zulip"
parameter = "8400f5f0-fad6-42a2-a985-3048402c7f2d"
notification_parameter.setdefault(plugin,{})[parameter] = {
    "general":{"description":"Zulip · 17-it-secops","comment":"","docu_url":""}, "parameter_properties":{},
}
notification_rules.append({
    "rule_id":"e1e2f4ba-a07a-4f2d-887b-ebbd9893dfcf","allow_disable":False,"contact_all":False,
    "contact_all_with_email":False,"contact_object":False,"contact_users":["cmkadmin"],"description":"Zulip TEST",
    "disabled":False,"notify_plugin":(plugin,parameter),"match_hosts":["polarita-hq"],
    "match_service_event":["rc","wc","uc","?c","cr"],"match_host_event":["rd","ud","?d","dr"],
})
