import sqlite3, tempfile, threading, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import budget

class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=sqlite3.connect(str(Path(self.tmp.name)/'state.sqlite'),check_same_thread=False); self.db.row_factory=sqlite3.Row; budget.ensure(self.db); self.db.execute("UPDATE budget_config SET value=\'20000000\' WHERE key=\'limit_micro_eur\'"); self.db.commit()
    def tearDown(self): self.db.close(); self.tmp.cleanup()
    def test_double_submit_is_blocked(self):
        budget.reserve(self.db,'same','voice',1000000)
        self.assertRaisesRegex(RuntimeError,'operation_key_exists',budget.reserve,self.db,'same','voice',1000000)
    def test_unknown_outcome_blocks_reuse(self):
        budget.reserve(self.db,'op','research',1000000); budget.settle(self.db,'op','uncertain'); self.assertEqual(self.db.execute("select status from budget_reservations where operation_key='op'").fetchone()[0],'uncertain'); self.assertRaisesRegex(RuntimeError,'operation_key_exists',budget.reserve,self.db,'op','research',1000000)
    def test_limit_does_not_roll_over_or_reset(self):
        budget.reserve(self.db,'a','video',19_000_000)
        with self.assertRaisesRegex(RuntimeError,'budget_exceeded'): budget.reserve(self.db,'b','voice',2_000_000)
        budget.settle(self.db,'a','committed',18_000_000)
        self.assertEqual(self.db.execute("select sum(committed_micro_eur) from budget_reservations").fetchone()[0],18_000_000)
        with self.assertRaisesRegex(RuntimeError,'budget_exceeded'): budget.reserve(self.db,'c','voice',3_000_000)
    def test_concurrent_reservations_are_serialized(self):
        results=[]; lock=threading.Lock()
        def run(i):
            c=sqlite3.connect(self.db.execute('pragma database_list').fetchone()[2],timeout=5); c.row_factory=sqlite3.Row
            try: budget.reserve(c,f'op{i}','video',12_000_000); out='ok'
            except RuntimeError: out='blocked'
            with lock: results.append(out)
            c.close()
        ts=[threading.Thread(target=run,args=(i,)) for i in (1,2)]; [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(results.count('ok'),1)

    def test_committed_amount_cannot_be_rewritten(self):
        budget.reserve(self.db,'immutable','voice',1_000_000)
        budget.settle(self.db,'immutable','committed',900_000)
        with self.assertRaisesRegex(RuntimeError,'reservation_already_settled'):
            budget.settle(self.db,'immutable','committed',0)
        self.assertEqual(budget.balance(self.db)['used_micro_eur'],900_000)

    def test_existing_limit_is_not_reset_by_policy(self):
        budget.ensure(self.db)
        self.assertEqual(budget.balance(self.db)['limit_micro_eur'],20_000_000)

    def test_initial_limit_comes_from_current_policy(self):
        fresh=sqlite3.connect(':memory:'); fresh.row_factory=sqlite3.Row
        try:
            budget.ensure(fresh)
            self.assertEqual(budget.balance(fresh)['limit_micro_eur'],25_000_000)
        finally:
            fresh.close()

    def test_explicit_limit_update_preserves_spending(self):
        budget.reserve(self.db,'paid','video',2_000_000)
        budget.settle(self.db,'paid','committed',1_000_000)
        budget.set_limit(self.db,25_000_000,'Confirmed first-test buffer')
        self.assertEqual(budget.balance(self.db)['used_micro_eur'],1_000_000)
        self.assertEqual(budget.balance(self.db)['limit_micro_eur'],25_000_000)
        self.assertEqual(self.db.execute('SELECT count(*) FROM budget_limit_changes').fetchone()[0],1)

    def test_limit_update_cannot_exceed_policy_or_erase_spending(self):
        with self.assertRaisesRegex(ValueError,'exceeds_saved_policy'):
            budget.set_limit(self.db,30_000_000,'Not authorized')
        budget.reserve(self.db,'held','voice',2_000_000)
        with self.assertRaisesRegex(ValueError,'below_existing_usage'):
            budget.set_limit(self.db,1_000_000,'Too low')

if __name__=='__main__': unittest.main()
