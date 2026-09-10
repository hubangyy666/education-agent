"""Meaningful offline checks against the real grader. No database mutations."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from backend import factory_agent as f

def question(sid='A10-S1', n=1):
    return dict(id=f'q{n}', type='choice', skill_id=sid, title=f'{sid}第{n}个测试场景的决策是什么？',
                project_rule=f'测试场景{n}须依据约定执行', options=['正确决策', '错误决策', '无关决策'],
                answer='正确决策', explanation='按给定约定执行', hint=['观察', '比较', '检查'],
                source_url='https://example.org/evidence', evidence=[{'source_url':'https://example.org/evidence'}])

class FactoryChecks(unittest.TestCase):
    def test_id_version_and_option_shuffle_cannot_create_new_content(self):
        q = question(); changed = deepcopy(q)
        changed.update(id='new-id', version=99, skill_id='A10-S4')
        changed['options'].reverse()
        self.assertEqual(f.content_hash(q), f.content_hash(changed))
        changed['options'][-1] = '改写的干扰项'
        self.assertEqual(f.content_hash(q), f.content_hash(changed))

    def test_image_rewording_is_duplicate(self):
        q = dict(type='box', title='框选目标', sample_sha256='pixelhash', answer=[{'box':[.1,.1,.3,.3], 'label':'猫'}], project_rule='可见外接框')
        self.assertEqual(f.content_hash(q), f.content_hash(dict(q, title='请把目标框出来', id='different')))
        changed=deepcopy(q); changed['answer'][0]['annotation_id']=123456
        self.assertEqual(f.content_hash(q), f.content_hash(changed))
        poly=dict(type='polygon', sample_sha256='pixels', project_rule='可见轮廓', answer={'label':'猫','polygon':[[.1,.1],[.8,.1],[.7,.8]]})
        reverse=deepcopy(poly); reverse['answer']['polygon'].reverse()
        self.assertEqual(f.content_hash(poly),f.content_hash(reverse))

    def test_grader_positive_and_negative_controls(self):
        q = question(); self.assertTrue(f.validate_question(q, q['skill_id'], q['evidence']))
        q['answer'] = '不在选项内'
        with self.assertRaises(ValueError): f.validate_question(q, q['skill_id'], q['evidence'])
        q = question(); q['source_url'] = 'https://invented.invalid/'
        with self.assertRaises(ValueError): f.validate_question(q, q['skill_id'], q['evidence'])

    def test_skill_balance_unique_content_and_version_rotation(self):
        with tempfile.TemporaryDirectory() as d:
            store = f.Store(d); rows = []
            for i in range(5):
                for n in range(12):
                    q = question(f'A10-S{i+1}', n)
                    q.update(status='approved', content_hash=f.content_hash(q),
                             ai_review={'decision':'approved', 'duplicate':False,
                                        'independent_answer':q['answer'], **{k:1.0 for k in f.QUALITY_MIN}})
                    rows.append(q)
            store.merge('A10', rows)
            pool = f.build_pool('A10', 1, store)
            all_q = [q for qs in pool.values() for q in qs]
            self.assertEqual(len(all_q), 55)
            self.assertEqual(len({q['content_hash'] for q in all_q}), 55)
            self.assertEqual(set(f.Counter(q['skill_id'] for q in all_q).values()), {11})
            job = pool['A10-JOB']; self.assertEqual(set(f.Counter(q['skill_id'] for q in job).values()), {4})
            next_pool = f.build_pool('A10', 2, store)
            self.assertNotEqual({q['content_hash'] for q in all_q}, {q['content_hash'] for qs in next_pool.values() for q in qs})

    def test_high_error_rate_only_flags_suspect(self):
        q=question(); runs=[]
        for i in range(10):
            runs.append(SimpleNamespace(id=str(i), username=f'u{i}', revision_of=None, status='completed',
                                        mode='job', questions=[q], answers={q['id']:{'value':'错误决策' if i<9 else q['answer']}}))
        self.assertFalse(next(iter(f.question_statistics(runs[:9]).values()))['suspect'])
        result=next(iter(f.question_statistics(runs).values()))
        self.assertTrue(result['suspect']); self.assertEqual(result['error_rate'], .9)
        self.assertNotIn('retired', result)
        unanswered=deepcopy(runs[-1]); unanswered.id='timeout'; unanswered.answers={}
        self.assertEqual(next(iter(f.question_statistics(runs+[unanswered]).values()))['sample_count'],10)

    def test_review_must_independently_solve_correct_answer(self):
        q=question(); r={'decision':'approved','duplicate':False,'independent_answer':'错误决策', **{k:1 for k in f.QUALITY_MIN}}
        self.assertFalse(f.approve_review(q,r))
        r['independent_answer']=q['answer']; self.assertTrue(f.approve_review(q,r))
        r['duplicate']=True; self.assertFalse(f.approve_review(q,r))

if __name__=='__main__': unittest.main()
