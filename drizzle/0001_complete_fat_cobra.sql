CREATE TABLE `mobile_accounts` (
	`employee_id` integer PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`salt` text NOT NULL,
	`pin_hash` text NOT NULL,
	`enabled` integer DEFAULT 1 NOT NULL,
	`failed` integer DEFAULT 0 NOT NULL,
	`locked_until` text,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `mobile_account_owner` ON `mobile_accounts` (`owner`);--> statement-breakpoint
CREATE TABLE `mobile_sessions` (
	`token_hash` text PRIMARY KEY NOT NULL,
	`employee_id` integer NOT NULL,
	`owner` text NOT NULL,
	`expires` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `mobile_session_employee` ON `mobile_sessions` (`employee_id`);