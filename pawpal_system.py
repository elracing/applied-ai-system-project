from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: str  # "low"|"medium"|"high"
    category: str = "general"  # walk/feed/meds/enrichment/grooming
    required: bool = True
    description: Optional[str] = None
    completed: bool = False
    time: Optional[str] = None  # optional scheduled time in "HH:MM" format
    frequency: str = "none"  # none|daily|weekly

    def __post_init__(self):
        """Validate Task fields after initialization."""
        valid_priorities = {"low", "medium", "high"}
        if self.priority not in valid_priorities:
            raise ValueError(f"Invalid priority '{self.priority}'; choose from {valid_priorities}")

        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be > 0")

        if not self.title.strip():
            raise ValueError("title cannot be empty")

    def estimate_effort(self) -> int:
        """Return numeric effort level for priority."""
        mapping = {"low": 1, "medium": 2, "high": 3}
        return mapping[self.priority]

    def summary(self) -> str:
        """Return a one-line summary of the task."""
        req = "required" if self.required else "optional"
        status = "done" if self.completed else "pending"
        time_str = f", starts at {self.time}" if self.time else ""
        return f"{self.title} ({self.duration_minutes}m, {self.priority}, {req}, {status}{time_str})"

    def mark_complete(self) -> Optional["Task"]:
        """Mark the task as complete and return a next occurrence for recurring tasks."""
        self.completed = True
        if self.frequency in {"daily", "weekly"}:
            return self._next_occurrence()
        return None

    def _next_occurrence(self) -> "Task":
        """Return a new Task instance for the next recurrence."""
        if self.frequency not in {"daily", "weekly"}:
            raise ValueError("No recurrence for non-recurring task")

        next_task = Task(
            title=self.title,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            category=self.category,
            required=self.required,
            description=self.description,
            completed=False,
            time=self.time,
            frequency=self.frequency,
        )

        return next_task

    def set_time(self, hhmm: str) -> None:
        """Set task time in HH:MM format."""
        self.time = hhmm


@dataclass
class Dog:
    name: str
    species: str
    age: Optional[int] = None
    breed: Optional[str] = None
    size: Optional[str] = None
    energy_level: Optional[str] = None  # low/medium/high
    needs_medication: bool = False
    tasks: List[Task] = field(default_factory=list)

    def __post_init__(self):
        """Validate Dog fields after initialization."""
        if not self.name.strip():
            raise ValueError("Dog name cannot be empty")

        if self.species.lower() not in {"dog", "cat", "other"}:
            raise ValueError("species must be 'dog', 'cat', or 'other'")

    def need_summary(self) -> str:
        """Return a text summary of the dog's needs."""
        base = f"{self.name} ({self.species})"
        if self.needs_medication:
            base += ", needs medication"
        if self.energy_level:
            base += f", energy={self.energy_level}"
        return base

    def is_high_energy(self) -> bool:
        """Return True when the dog's energy is high."""
        return (self.energy_level or "").lower() == "high"

    def add_task(self, task: Task) -> None:
        """Add a task to the dog's task list."""
        self.tasks.append(task)

    def remove_task(self, task: Task) -> None:
        """Remove a task from the dog's task list."""
        self.tasks = [t for t in self.tasks if t != task]

    @property
    def task_count(self) -> int:
        """Return the number of tasks assigned to the dog."""
        return len(self.tasks)


@dataclass
class Owner:
    name: str
    email: Optional[str] = None
    available_minutes_per_day: int = 60
    tasks: List[Task] = field(default_factory=list)
    preferences: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate Owner fields after initialization."""
        if not self.name.strip():
            raise ValueError("Owner name cannot be empty")

        if self.available_minutes_per_day <= 0:
            raise ValueError("available_minutes_per_day must be positive")

    def add_task(self, task: Task) -> None:
        """Add a task to the owner's task list."""
        self.tasks.append(task)

    def remove_task(self, task: Task) -> None:
        """Remove a task from the owner's task list."""
        self.tasks = [t for t in self.tasks if t != task]

    def get_priority_tasks(self, min_priority: str = "medium") -> List[Task]:
        """Return tasks with priority >= minimum threshold."""
        order = {"low": 0, "medium": 1, "high": 2}
        thresh = order.get(min_priority, 1)
        return [t for t in self.tasks if order.get(t.priority, 0) >= thresh]

    def summary(self) -> str:
        """Return a summary of the owner's status."""
        return (
            f"{self.name} has {len(self.tasks)} tasks, "
            f"{self.available_minutes_per_day} available minutes/day"
        )


@dataclass
class DailyPlan:
    owner: Owner
    dog: Dog
    day: date = field(default_factory=date.today)
    scheduled_tasks: List[Task] = field(default_factory=list)
    total_time_minutes: int = 0
    explanation: Optional[str] = None

    def add_task(self, task: Task) -> None:
        """Add a task to the schedule if it is not already included."""
        if task not in self.scheduled_tasks:
            self.scheduled_tasks.append(task)
            self.total_time_minutes += task.duration_minutes

    def remove_task(self, task: Task) -> None:
        """Remove a task from the schedule and recalc total time."""
        self.scheduled_tasks = [t for t in self.scheduled_tasks if t != task]
        self.total_time_minutes = sum(t.duration_minutes for t in self.scheduled_tasks)

    def generate_schedule(self, available_minutes: Optional[int] = None) -> None:
        """Generate a schedule from owner tasks, respecting time limits and priorities."""
        if available_minutes is None:
            available_minutes = self.owner.available_minutes_per_day

        if available_minutes <= 0:
            raise ValueError("available_minutes must be positive")

        order = {"low": 0, "medium": 1, "high": 2}

        required_tasks = [t for t in self.owner.tasks if t.required]
        optional_tasks = [t for t in self.owner.tasks if not t.required]

        required_tasks.sort(key=lambda t: order[t.priority], reverse=True)
        optional_tasks.sort(key=lambda t: order[t.priority], reverse=True)

        self.scheduled_tasks.clear()
        self.total_time_minutes = 0

        def try_add(task: Task) -> bool:
            if self.total_time_minutes + task.duration_minutes <= available_minutes:
                self.scheduled_tasks.append(task)
                self.total_time_minutes += task.duration_minutes
                return True
            return False

        for task in required_tasks:
            if not try_add(task):
                raise RuntimeError(
                    f"Cannot fit required task {task.title} in available time ({available_minutes}m)"
                )

        for task in optional_tasks:
            try_add(task)

        self.explanation = self._build_explanation(available_minutes)

    def _build_explanation(self, available_minutes: int) -> str:
        """Build a human-friendly explanation text for the generated schedule."""
        lines = [
            f"Daily plan for {self.owner.name} and {self.dog.name} on {self.day.isoformat()}",
            f"Allocated {self.total_time_minutes}/{available_minutes} minutes",
            "Scheduled tasks:",
        ]

        for task in self.scheduled_tasks:
            lines.append(f"- {task.summary()}")

        if self.total_time_minutes < available_minutes:
            slack = available_minutes - self.total_time_minutes
            lines.append(f"Time slack: {slack} minutes remaining")

        return "\n".join(lines)

    def explain_plan(self) -> str:
        """Return the written plan explanation or a placeholder if none."""
        if self.explanation is None:
            return "No plan generated yet."
        return self.explanation

    def check_conflicts(self) -> List[str]:
        """Return warning messages for tasks scheduled at overlapping times."""
        warnings: List[str] = []
        time_map = {}

        for task in self.scheduled_tasks:
            if task.time is None:
                continue
            time_map.setdefault(task.time, []).append(task)

        for time_slot, tasks in time_map.items():
            if len(tasks) > 1:
                pet_names = set((t.description or "unknown").strip() for t in tasks)
                warning = (
                    f"Conflict at {time_slot}: {len(tasks)} tasks scheduled at same time (" 
                    + ", ".join(t.title for t in tasks)
                    + ") for pets: "
                    + ", ".join(sorted(pet_names))
                )
                warnings.append(warning)

        return warnings

    def mark_task_complete(self, task: Task) -> None:
        """Mark a scheduled task complete (and enqueue next occurrence if recurring)."""
        if task not in self.scheduled_tasks:
            raise ValueError("Task is not in today's schedule")

        next_task = task.mark_complete()
        self.remove_task(task)

        if next_task is not None:
            self.owner.add_task(next_task)

    def sort_by_time(self, ascending: bool = True) -> None:
        """Sort scheduled tasks by their time field (HH:MM)."""
        # Using lambda key with HH:MM will naturally sort lexicographically as time strings
        # e.g. '08:15' < '09:30' < '14:45'.
        timed = sorted(
            [t for t in self.scheduled_tasks if t.time],
            key=lambda task: task.time,
            reverse=not ascending,
        )
        untimed = [t for t in self.scheduled_tasks if not t.time]
        self.scheduled_tasks = timed + untimed

    def filter_tasks(self, completed: Optional[bool] = None, pet_name: Optional[str] = None) -> List[Task]:
        """Filter scheduled tasks by completion status and/or pet name in description."""
        result = self.scheduled_tasks

        if completed is not None:
            result = [t for t in result if t.completed == completed]

        if pet_name is not None:
            result = [t for t in result if t.description and pet_name.lower() in t.description.lower()]

        return result


