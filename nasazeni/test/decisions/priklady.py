"""Připraví tři rozpoznatelné vzorové položky přes skutečné API Paperclipu."""
import json
import sys
from uuid import UUID, uuid5

from board import Board


def proposals():
    namespace = UUID('cdc8422c-af52-4c76-8128-67f93cab1364')
    for num, title, expected in ((11, 'Zkouška potvrzení', 'approved'), (12, 'Zkouška zamítnutí', 'rejected'),
                                  (13, 'Vyzkoušet rozhodnutí ve vzorovém spisu', None)):
        case = f'TEST-POL-0000-{num:05d}'
        key = str(uuid5(namespace, case))
        payload = {
            'title': f'{title} · {case}',
            'summary': 'Vzorový spis je rozpracován, verze 1. Návrh jej přesune do stavu „ke kontrole“, verze 2.',
            'recommendedAction': 'Porovnej oba stavy. Approve potvrdí změnu, Reject zachová původní stav.',
            'nextActionOnApproval': 'Testovací databáze ověří původní verzi a zaznamená změnu spisu.',
            'polarita': {'test': True, 'id': key, 'spis': case, 'fronta': 'URGENT',
                         'pred': {'stav': 'rozpracován', 'verze': 1}, 'po': {'stav': 'ke kontrole', 'verze': 2}},
        }
        yield key, payload, expected


def main():
    fqdn, mode = sys.argv[1:]
    if mode not in ('priprav', 'vyzkousej'):
        raise ValueError('Neznámý režim')
    board = Board(fqdn)
    reviewer = board.login(sys.stdin.readline().rstrip('\r\n'))
    try:
        company, = [c for c in board.call('GET', '/api/companies') if c['name']=='Polarita s.r.o.'
                    and c['budgetMonthlyCents']==47000]
        path = f"/api/companies/{company['id']}/approvals"
        existing = board.call('GET', path)
        manifest = []
        for key, payload, expect in proposals():
            matches = [a for a in existing if (a['payload'].get('polarita') or {}).get('id')==key]
            if not matches and mode=='priprav':
                matches.append(board.call('POST', path, {'type':'request_board_approval','payload':payload},
                                          allowed=(201,)))
            a, = matches
            if (a['companyId']!=company['id'] or a['type']!='request_board_approval' or a['payload']!=payload
                    or a.get('requestedByAgentId') is not None or a.get('requestedByUserId')!=reviewer):
                raise RuntimeError('Nesouhlasí vlastník nebo obsah vzorového schválení')
            approval = str(UUID(a['id']))
            if mode=='vyzkousej' and expect:
                if a['status']=='pending':
                    action = {'approved':'approve', 'rejected':'reject'}[expect]
                    board.call('POST', f'/api/approvals/{approval}/{action}',
                               {'decisionNote':'Automatická přejímací zkouška na označeném vzorovém spisu.'})
                final = board.call('GET', f'/api/approvals/{approval}')
                if final['status']!=expect or final.get('decidedByUserId')!=reviewer:
                    raise RuntimeError('Nativní hlasování nepotvrdilo očekávaný účet a volbu')
            manifest.append({'approval':approval,'company':company['id'],'spravce':reviewer,'obsah':payload})
        if mode=='priprav':
            print(json.dumps(manifest, ensure_ascii=False))
    finally:
        board.call('POST','/api/auth/sign-out',{})


if __name__=='__main__':
    main()
