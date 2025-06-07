# 🚀 Quick Reference: Chiropractor → Care Provider Changes

_Quick lookup guide for developers working with the updated terminology_

## 🔄 **Database Changes**

### Fields

```sql
-- BEFORE
chiropractor_id

-- AFTER
care_provider_id
```

### Role Names

```sql
-- BEFORE
'chiropractor'

-- AFTER
'care_provider'
```

## 📡 **API Changes**

### CRUD Functions

```python
# BEFORE
get_plans_by_chiropractor(chiropractor_id)
associate_user_with_chiropractor(user_id, chiropractor_id)

# AFTER
get_plans_by_care_provider(care_provider_id)
associate_user_with_care_provider(user_id, care_provider_id)
```

### Schema Imports

```python
# BEFORE
from api.schemas.plan import TherapyPlanCreate
# (uses chiropractor_id internally)

# AFTER
from api.schemas.plan import TherapyPlanCreate
# (now uses care_provider_id internally)
```

### Role Enum

```python
# BEFORE
RoleType.CHIROPRACTOR

# AFTER
RoleType.CARE_PROVIDER
```

## 🗄️ **Model Relationships**

### TherapyPlan Model

```python
# BEFORE
class TherapyPlan(Base):
    chiropractor_id = Column(Integer, ForeignKey("users.user_id"))

# AFTER
class TherapyPlan(Base):
    care_provider_id = Column(Integer, ForeignKey("users.user_id"))
```

## ⚙️ **Configuration**

### Project Names

```python
# BEFORE
PROJECT_NAME = "Tirado Chiro API"

# AFTER
PROJECT_NAME = "Tirado Care Provider API"
```

## 🧪 **Testing**

### Role Checks

```python
# BEFORE
user.has_role("chiropractor")

# AFTER
user.has_role("care_provider")
```

## 📱 **Frontend Integration Points**

### API Requests

```javascript
// BEFORE
{
  chiropractor_id: 123;
}

// AFTER
{
  care_provider_id: 123;
}
```

### Role-Based UI

```javascript
// BEFORE
if (user.role === 'chiropractor')

// AFTER
if (user.role === 'care_provider')
```

---

## ⚡ **Key Files to Review**

| **Category** | **Files**                                        |
| ------------ | ------------------------------------------------ |
| **Models**   | `api/models/base.py`                             |
| **Schemas**  | `api/schemas/plan.py`, `api/schemas/user.py`     |
| **CRUD**     | `api/crud/crud_plan.py`, `api/crud/crud_user.py` |
| **Config**   | `api/core/config.py`                             |
| **Tests**    | `tests/conftest.py`                              |

---

## 🆘 **Need Help?**

- **QA Tests:** Run `python scripts/qa_regression_test_plan.py`
- **Full Documentation:** See `docs/TERMINOLOGY_REFACTORING_GUIDE.md`
- **Migration Scripts:** Check `alembic/versions/` directory

---

_Updated: June 7, 2025 | Status: Production Ready ✅_
