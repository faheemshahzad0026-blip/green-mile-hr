declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
    ATTENDANCE_BRIDGE_SECRET?:string;
    BUCKET?: R2Bucket;
  }
}
