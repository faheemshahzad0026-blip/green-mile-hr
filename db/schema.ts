import { sqliteTable, integer, text, index, uniqueIndex } from 'drizzle-orm/sqlite-core';
export const records = sqliteTable('hr_records', {
 id: integer('id').primaryKey({ autoIncrement: true }),
 owner: text('owner').notNull(), kind: text('kind').notNull(), data: text('data').notNull(),
 naturalKey: text('natural_key'), createdAt: text('created_at').notNull(), updatedAt: text('updated_at').notNull(),
}, t => [index('hr_owner_kind').on(t.owner,t.kind),uniqueIndex('hr_natural_key').on(t.owner,t.kind,t.naturalKey)]);
export const audit = sqliteTable('hr_audit', {id:integer('id').primaryKey({autoIncrement:true}),owner:text('owner').notNull(),action:text('action').notNull(),kind:text('kind').notNull(),recordId:text('record_id').notNull(),at:text('at').notNull()},t=>[index('audit_owner').on(t.owner)]);
export const mobileAccounts = sqliteTable('mobile_accounts', {employeeId:integer('employee_id').primaryKey(),owner:text('owner').notNull(),salt:text('salt').notNull(),pinHash:text('pin_hash').notNull(),enabled:integer('enabled').notNull().default(1),failed:integer('failed').notNull().default(0),lockedUntil:text('locked_until'),updatedAt:text('updated_at').notNull()},t=>[index('mobile_account_owner').on(t.owner)]);
export const mobileSessions = sqliteTable('mobile_sessions',{tokenHash:text('token_hash').primaryKey(),employeeId:integer('employee_id').notNull(),owner:text('owner').notNull(),expires:text('expires').notNull()},t=>[index('mobile_session_employee').on(t.employeeId)]);
