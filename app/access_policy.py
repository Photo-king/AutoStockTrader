"""Fail closed when Windows integrity cannot be established for desktop input."""


def require_input_integrity(report):
    probe=report.get('probe', {})
    targets=report.get('targets', {})
    if probe.get('status')!='read' or not isinstance(probe.get('rid'), int) or not targets:
        raise ValueError('Input refused: process integrity is unknown')
    for target in targets.values():
        if target.get('status')!='read' or not isinstance(target.get('rid'), int):
            raise ValueError('Input refused: target integrity is unknown')
        if probe['rid']<target['rid']:
            raise ValueError('Input refused: diagnostic integrity is lower than target; use an explicitly elevated diagnostic task')
