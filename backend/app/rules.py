"""The checks SiteSync runs, in plain language, and the settings a firm can change for each.

One place defines both what the rule engine does and what people are told about it, so the
explanation on screen can never drift from the behavior.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from .database import get_db
from .models import Audit
from .security import current_user, project_access, require_write

router = APIRouter()
Db, Auth = Depends(get_db), Depends(current_user)

EMAIL_WORDS = ['delay', 'lead time', 'backorder', 'late', 'expedited', 'missing', 'revised ship date', 'cannot install', 'awaiting approval']
SEVERITIES = ('high', 'medium', 'low')

DEFAULTS = {
    'release': {'enabled': True, 'severity': 'high', 'buffer_days': 0, 'released_statuses': ['released', 'ordered', 'delivered']},
    'delivery': {'enabled': True, 'severity': 'high'},
    'approval': {'enabled': True, 'severity': 'high'},
    'rfi': {'enabled': True, 'severity': 'medium', 'window_days': 21, 'urgent_days': 7},
    'overdue': {'enabled': True, 'severity': 'medium'},
    'email': {'enabled': True, 'severity': 'low', 'keywords': EMAIL_WORDS},
    'warn_days': 7,
}

# What each check means, in the words a project manager would use.
GUIDE = {
    'release': {
        'label': 'Order not released in time', 'icon': 'package',
        'what': 'Every material has a date it must be on site and a lead time. Subtract the lead time from the date and you get the latest day it could be released. Past that day with no order placed, it will arrive late.',
        'clears_when': 'The item is marked ordered, released or delivered, or its dates are corrected.',
        'steps': ['Call the vendor and confirm they can still hit the date, and ask about expediting.', 'Release the order, then set the item to Ordered on the Materials tab.', 'If the dates are wrong, fix them on the Materials tab. SiteSync re-checks right away.'],
        'settings': ['buffer_days', 'released_statuses', 'severity'],
    },
    'delivery': {
        'label': 'Material arrives after the work that needs it', 'icon': 'calendar',
        'what': 'An item is expected on site after a related activity is scheduled to start. Items and activities are matched by the links you set on the Materials tab, or by shared words in their names.',
        'clears_when': 'The delivery date moves earlier, the activity is resequenced, or the item is delivered.',
        'steps': ['Get a firm ship date from the vendor.', 'Ask the trade whether they can resequence around it.', 'Update the delivery date or the activity dates so the plan matches reality.'],
        'settings': ['severity'],
    },
    'approval': {
        'label': 'Procurement waiting on a submittal', 'icon': 'clipboard',
        'what': 'An item is past its latest release date and the submittal it depends on is not approved yet, so the order cannot go in.',
        'clears_when': 'The submittal is approved or closed, or the item is released.',
        'steps': ['Chase the reviewer named on the submittal for a committed return date.', 'Ask whether the order can be released at risk.', 'Record the approval on the Submittals list when it comes back.'],
        'settings': ['severity'],
    },
    'rfi': {
        'label': 'Open RFI near upcoming work', 'icon': 'file',
        'what': 'An RFI is still open and shares words with an activity that starts soon. It could be holding that work up, but only a person can confirm the dependency.',
        'clears_when': 'The RFI is answered or closed, or you confirm it does not affect that work and dismiss the item.',
        'steps': ['Ask the reviewer for a response date.', 'Confirm with the trade whether they can start without the answer.', 'Close the RFI when the response is in.'],
        'settings': ['window_days', 'urgent_days', 'severity'],
    },
    'overdue': {
        'label': 'Submittal review past due', 'icon': 'clipboard',
        'what': 'A submittal passed its review due date and is not approved or closed.',
        'clears_when': 'The submittal is approved or closed, or its due date is updated.',
        'steps': ['Follow up with the reviewer.', 'Agree a return date and update the due date.', 'Check what is waiting on this approval.'],
        'settings': ['severity'],
    },
    'email': {
        'label': 'Email mentions a possible constraint', 'icon': 'mail',
        'what': 'A project email contains words such as "delay" or "backorder". This is a keyword match, not a confirmed problem, so it is always low priority until someone reads it.',
        'clears_when': 'You read it and either act on it or dismiss it.',
        'steps': ['Read the email and confirm the constraint with the sender.', 'Link it to the affected activity or item.', 'Dismiss it if it is not a real issue.'],
        'settings': ['keywords', 'severity'],
    },
}

SETTING_LABELS = {
    'enabled': 'Check is on', 'severity': 'Priority', 'buffer_days': 'Warn this many days before the latest release date',
    'released_statuses': 'Statuses that count as released', 'window_days': 'Look this many days ahead for affected work',
    'urgent_days': 'Mark high priority when work starts within this many days', 'keywords': 'Words that flag an email', 'warn_days': 'Warn this many days before something is due',
}


def rule_config(project):
    """Defaults overlaid with whatever the firm set for this project."""
    saved = (project.settings or {}).get('rules') or {}
    out = {}
    for rule, default in DEFAULTS.items():
        if isinstance(default, dict):
            out[rule] = {**default, **{k: v for k, v in (saved.get(rule) or {}).items() if k in default}}
        else:
            out[rule] = saved.get(rule, default)
    return out


class RuleSettings(BaseModel):
    enabled: bool | None = None
    severity: str | None = None
    buffer_days: int | None = Field(default=None, ge=0, le=180)
    released_statuses: list[str] | None = Field(default=None, max_length=12)
    window_days: int | None = Field(default=None, ge=1, le=120)
    urgent_days: int | None = Field(default=None, ge=0, le=60)
    keywords: list[str] | None = Field(default=None, max_length=40)


class RulesBody(BaseModel):
    release: RuleSettings | None = None
    delivery: RuleSettings | None = None
    approval: RuleSettings | None = None
    rfi: RuleSettings | None = None
    overdue: RuleSettings | None = None
    email: RuleSettings | None = None
    warn_days: int | None = Field(default=None, ge=1, le=60)


@router.get('/api/rules/guide')
def guide(user=Auth):
    return {'rules': GUIDE, 'labels': SETTING_LABELS, 'defaults': DEFAULTS}


@router.get('/api/projects/{project_id}/rules')
def get_rules(project_id: str, db: Session = Db, user=Auth):
    project = project_access(db, user, project_id)
    return {'config': rule_config(project), 'defaults': DEFAULTS}


@router.put('/api/projects/{project_id}/rules')
def set_rules(project_id: str, body: RulesBody, db: Session = Db, user=Auth):
    require_write(user)
    project = project_access(db, user, project_id)
    current = rule_config(project)
    for rule, patch in body.model_dump(exclude_none=True).items():
        if rule == 'warn_days':
            current['warn_days'] = patch
            continue
        patch = {k: v for k, v in patch.items() if v is not None}
        if 'severity' in patch and patch['severity'] not in SEVERITIES:
            raise HTTPException(422, 'Priority must be high, medium or low.')
        if 'released_statuses' in patch:
            patch['released_statuses'] = sorted({s.strip().lower()[:40] for s in patch['released_statuses'] if s.strip()})
        if 'keywords' in patch:
            patch['keywords'] = sorted({s.strip().lower()[:60] for s in patch['keywords'] if s.strip()})
        current[rule] = {**current[rule], **patch}
    project.settings = {**(project.settings or {}), 'rules': current}
    db.add(Audit(organization_id=user.organization_id, user_id=user.id, action='rules.update', detail={'project_id': project_id}))
    db.flush()
    from .risk_engine import run_rules
    run_rules(db, project_id)  # the new settings apply to what is on screen straight away
    db.commit()
    return {'config': rule_config(project), 'defaults': DEFAULTS}
