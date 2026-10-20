import type { Metadata } from 'next';
import './globals.css';
export const metadata:Metadata={title:'Green Mile HR | UAE People & Payroll',description:'Private HR workspace for employee records, attendance, leave and payroll in the UAE.',icons:{icon:'/green-mile-logo.png',apple:'/green-mile-logo.png'},manifest:'/manifest.webmanifest',appleWebApp:{capable:true,title:'Green Mile HR',statusBarStyle:'default'}};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
