import pytest
from pawpal_system import DailyPlan, Dog, Owner, Task


# ── Task construction ─────────────────────────────────────────────────────────

class TestTaskConstruction:
    def test_empty_title_raises(self):
        with pytest.raises(ValueError, match="title cannot be empty"):
            Task(title="", duration_minutes=10, priority="low")

    def test_whitespace_only_title_raises(self):
        with pytest.raises(ValueError, match="title cannot be empty"):
            Task(title="   ", duration_minutes=10, priority="low")

    def test_invalid_priority_raises(self):
        with pytest.raises(ValueError, match="Invalid priority"):
            Task(title="Walk", duration_minutes=10, priority="urgent")

    def test_zero_duration_raises(self):
        with pytest.raises(ValueError, match="duration_minutes must be > 0"):
            Task(title="Walk", duration_minutes=0, priority="low")

    def test_negative_duration_raises(self):
        with pytest.raises(ValueError):
            Task(title="Walk", duration_minutes=-5, priority="low")

    def test_effort_ordering(self):
        low = Task(title="A", duration_minutes=5, priority="low")
        med = Task(title="B", duration_minutes=5, priority="medium")
        high = Task(title="C", duration_minutes=5, priority="high")
        assert low.estimate_effort() < med.estimate_effort() < high.estimate_effort()


# ── Dog construction ──────────────────────────────────────────────────────────

class TestDogConstruction:
    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name cannot be empty"):
            Dog(name="", species="dog")

    def test_whitespace_name_raises(self):
        with pytest.raises(ValueError, match="name cannot be empty"):
            Dog(name="   ", species="dog")

    def test_invalid_species_raises(self):
        with pytest.raises(ValueError, match="species"):
            Dog(name="Mochi", species="fish")

    def test_remove_task_decrements_count(self):
        dog = Dog(name="Mochi", species="dog")
        t = Task(title="Walk", duration_minutes=20, priority="high")
        dog.add_task(t)
        dog.remove_task(t)
        assert dog.task_count == 0

    def test_remove_nonexistent_task_is_safe(self):
        dog = Dog(name="Mochi", species="dog")
        t = Task(title="Walk", duration_minutes=20, priority="high")
        dog.remove_task(t)
        assert dog.task_count == 0


# ── Owner ─────────────────────────────────────────────────────────────────────

class TestOwner:
    def test_empty_name_raises(self):
        with pytest.raises(ValueError):
            Owner(name="")

    def test_zero_minutes_raises(self):
        with pytest.raises(ValueError):
            Owner(name="Jordan", available_minutes_per_day=0)

    def test_negative_minutes_raises(self):
        with pytest.raises(ValueError):
            Owner(name="Jordan", available_minutes_per_day=-10)

    def test_get_priority_tasks_high_threshold(self):
        owner = Owner(name="Jordan", available_minutes_per_day=120)
        low = Task(title="Low", duration_minutes=5, priority="low")
        med = Task(title="Med", duration_minutes=5, priority="medium")
        high = Task(title="High", duration_minutes=5, priority="high")
        owner.add_task(low)
        owner.add_task(med)
        owner.add_task(high)
        result = owner.get_priority_tasks("high")
        assert high in result
        assert med not in result
        assert low not in result

    def test_get_priority_tasks_medium_threshold(self):
        owner = Owner(name="Jordan", available_minutes_per_day=120)
        low = Task(title="Low", duration_minutes=5, priority="low")
        med = Task(title="Med", duration_minutes=5, priority="medium")
        high = Task(title="High", duration_minutes=5, priority="high")
        owner.add_task(low)
        owner.add_task(med)
        owner.add_task(high)
        result = owner.get_priority_tasks("medium")
        assert high in result
        assert med in result
        assert low not in result


# ── DailyPlan scheduling ──────────────────────────────────────────────────────

class TestScheduling:
    def _setup(self, minutes=120):
        owner = Owner(name="Jordan", available_minutes_per_day=minutes)
        dog = Dog(name="Mochi", species="dog")
        plan = DailyPlan(owner=owner, dog=dog)
        return plan, owner, dog

    def test_required_task_exceeds_time_raises(self):
        plan, owner, _ = self._setup(minutes=10)
        owner.add_task(Task(title="Long walk", duration_minutes=60, priority="high", required=True))
        with pytest.raises(RuntimeError, match="Cannot fit required task"):
            plan.generate_schedule()

    def test_optional_task_dropped_when_time_full(self):
        plan, owner, _ = self._setup(minutes=30)
        owner.add_task(Task(title="Required", duration_minutes=30, priority="high", required=True))
        owner.add_task(Task(title="Optional", duration_minutes=10, priority="low", required=False))
        plan.generate_schedule()
        titles = [t.title for t in plan.scheduled_tasks]
        assert "Required" in titles
        assert "Optional" not in titles

    def test_no_tasks_produces_empty_schedule(self):
        plan, _, _ = self._setup()
        plan.generate_schedule()
        assert plan.scheduled_tasks == []
        assert plan.total_time_minutes == 0

    def test_high_priority_scheduled_first(self):
        plan, owner, _ = self._setup(minutes=30)
        owner.add_task(Task(title="Low", duration_minutes=10, priority="low", required=True))
        owner.add_task(Task(title="High", duration_minutes=10, priority="high", required=True))
        plan.generate_schedule()
        assert plan.scheduled_tasks[0].title == "High"

    def test_total_time_correct_after_schedule(self):
        plan, owner, _ = self._setup(minutes=120)
        owner.add_task(Task(title="A", duration_minutes=20, priority="high"))
        owner.add_task(Task(title="B", duration_minutes=30, priority="medium"))
        plan.generate_schedule()
        assert plan.total_time_minutes == 50

    def test_duplicate_task_not_added_twice(self):
        plan, _, _ = self._setup()
        t = Task(title="Walk", duration_minutes=20, priority="high")
        plan.add_task(t)
        plan.add_task(t)
        assert len(plan.scheduled_tasks) == 1
        assert plan.total_time_minutes == 20

    def test_remove_task_updates_total_time(self):
        plan, owner, _ = self._setup()
        t = Task(title="Walk", duration_minutes=20, priority="high")
        owner.add_task(t)
        plan.generate_schedule()
        plan.remove_task(t)
        assert plan.total_time_minutes == 0
        assert t not in plan.scheduled_tasks

    def test_mark_complete_task_not_in_schedule_raises(self):
        plan, _, _ = self._setup()
        t = Task(title="Walk", duration_minutes=20, priority="high")
        with pytest.raises(ValueError, match="not in today's schedule"):
            plan.mark_task_complete(t)

    def test_non_recurring_complete_no_next_task_added(self):
        plan, owner, _ = self._setup()
        t = Task(title="Walk", duration_minutes=20, priority="high", frequency="none")
        owner.add_task(t)
        plan.generate_schedule()
        count_before = len(owner.tasks)
        plan.mark_task_complete(t)
        assert len(owner.tasks) == count_before

    def test_explicit_zero_available_minutes_raises(self):
        plan, owner, _ = self._setup(minutes=60)
        with pytest.raises(ValueError, match="available_minutes must be positive"):
            plan.generate_schedule(available_minutes=0)


# ── sort_by_time ──────────────────────────────────────────────────────────────

class TestSortByTime:
    def _plan_with_tasks(self, *tasks, minutes=120):
        owner = Owner(name="Jordan", available_minutes_per_day=minutes)
        dog = Dog(name="Mochi", species="dog")
        plan = DailyPlan(owner=owner, dog=dog)
        for t in tasks:
            owner.add_task(t)
        plan.generate_schedule()
        return plan

    def test_untimed_tasks_not_dropped(self):
        timed = Task(title="Timed", duration_minutes=10, priority="low", time="09:00")
        untimed = Task(title="Untimed", duration_minutes=10, priority="low")
        plan = self._plan_with_tasks(timed, untimed)
        plan.sort_by_time()
        titles = [t.title for t in plan.scheduled_tasks]
        assert "Timed" in titles
        assert "Untimed" in titles

    def test_timed_tasks_appear_before_untimed(self):
        untimed = Task(title="Untimed", duration_minutes=10, priority="high")
        timed = Task(title="Timed", duration_minutes=10, priority="low", time="08:00")
        plan = self._plan_with_tasks(untimed, timed)
        plan.sort_by_time()
        assert plan.scheduled_tasks[0].title == "Timed"
        assert plan.scheduled_tasks[-1].title == "Untimed"

    def test_all_untimed_tasks_preserved(self):
        tasks = [Task(title=f"Task {i}", duration_minutes=10, priority="low") for i in range(3)]
        plan = self._plan_with_tasks(*tasks)
        plan.sort_by_time()
        assert len(plan.scheduled_tasks) == 3


# ── check_conflicts ───────────────────────────────────────────────────────────

class TestCheckConflicts:
    def test_no_conflicts_when_no_time_set(self):
        owner = Owner(name="Jordan", available_minutes_per_day=120)
        dog = Dog(name="Mochi", species="dog")
        plan = DailyPlan(owner=owner, dog=dog)
        owner.add_task(Task(title="A", duration_minutes=10, priority="high"))
        owner.add_task(Task(title="B", duration_minutes=10, priority="high"))
        plan.generate_schedule()
        assert plan.check_conflicts() == []

    def test_no_conflicts_different_times(self):
        owner = Owner(name="Jordan", available_minutes_per_day=120)
        dog = Dog(name="Mochi", species="dog")
        plan = DailyPlan(owner=owner, dog=dog)
        owner.add_task(Task(title="A", duration_minutes=10, priority="high", time="08:00"))
        owner.add_task(Task(title="B", duration_minutes=10, priority="high", time="09:00"))
        plan.generate_schedule()
        assert plan.check_conflicts() == []

    def test_three_tasks_same_slot_reports_one_conflict(self):
        owner = Owner(name="Jordan", available_minutes_per_day=120)
        dog = Dog(name="Mochi", species="dog")
        plan = DailyPlan(owner=owner, dog=dog)
        for title in ["A", "B", "C"]:
            owner.add_task(Task(title=title, duration_minutes=10, priority="high", time="09:00"))
        plan.generate_schedule()
        conflicts = plan.check_conflicts()
        assert len(conflicts) == 1
        assert "3 tasks" in conflicts[0]
