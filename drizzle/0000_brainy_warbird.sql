CREATE TABLE `hr_audit` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`owner` text NOT NULL,
	`action` text NOT NULL,
	`kind` text NOT NULL,
	`record_id` text NOT NULL,
	`at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `audit_owner` ON `hr_audit` (`owner`);--> statement-breakpoint
CREATE TABLE `hr_records` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`owner` text NOT NULL,
	`kind` text NOT NULL,
	`data` text NOT NULL,
	`natural_key` text,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `hr_owner_kind` ON `hr_records` (`owner`,`kind`);--> statement-breakpoint
CREATE UNIQUE INDEX `hr_natural_key` ON `hr_records` (`owner`,`kind`,`natural_key`);