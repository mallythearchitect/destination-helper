-- The fifth onboarding question (v5 of the brief): how much the app should
-- handle, and whether it may message or call businesses for you.
ALTER TABLE trips ADD COLUMN handling TEXT NOT NULL DEFAULT 'check_my_plan';   -- plan_for_me | check_my_plan | just_remind
ALTER TABLE trips ADD COLUMN may_contact INTEGER NOT NULL DEFAULT 0;           -- 1 = it may message, then call, businesses on your behalf
