package net.greenmile.attendance;
public class PdfProvider extends android.content.ContentProvider {
 public boolean onCreate(){return true;}
 private java.io.File file(android.net.Uri uri){String name=uri.getLastPathSegment();if(!"net.greenmile.attendance.pdf".equals(uri.getAuthority())||name==null||!name.matches("Green_Mile_(Salary|Attendance|Certificate)_[0-9]{5,10}_[0-9-]+\\.pdf"))throw new IllegalArgumentException("Invalid PDF");return new java.io.File(new java.io.File(getContext().getCacheDir(),"salary-pdfs"),name);}
 public String getType(android.net.Uri uri){file(uri);return "application/pdf";}
 public android.os.ParcelFileDescriptor openFile(android.net.Uri uri,String mode)throws java.io.FileNotFoundException{if(!"r".equals(mode))throw new java.io.FileNotFoundException("Read only");return android.os.ParcelFileDescriptor.open(file(uri),android.os.ParcelFileDescriptor.MODE_READ_ONLY);}
 public android.database.Cursor query(android.net.Uri uri,String[] projection,String selection,String[] args,String sort){java.io.File f=file(uri);String[] cols=projection!=null?projection:new String[]{"_display_name","_size"};android.database.MatrixCursor c=new android.database.MatrixCursor(cols);Object[] row=new Object[cols.length];for(int i=0;i<cols.length;i++)row[i]="_display_name".equals(cols[i])?f.getName():"_size".equals(cols[i])?f.length():null;c.addRow(row);return c;}
 public android.net.Uri insert(android.net.Uri u,android.content.ContentValues v){throw new UnsupportedOperationException();}public int delete(android.net.Uri u,String s,String[] a){throw new UnsupportedOperationException();}public int update(android.net.Uri u,android.content.ContentValues v,String s,String[] a){throw new UnsupportedOperationException();}
}
