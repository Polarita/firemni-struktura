# Vlastní zdroj agentových dat přijímá čtecí výstup z VM přes Incus.
all_hosts += ["polarita-hq|tcp"]
ipaddresses.update({"polarita-hq":"127.0.0.1"})
datasource_programs.insert(0, {
    "condition": {"host_name": ["polarita-hq"]},
    "value": "/usr/bin/python3 /usr/local/lib/polarita-dohled/agent.py",
    "id": "5522eeea-f93c-48fb-af7f-91fb4b61fb58",
})
