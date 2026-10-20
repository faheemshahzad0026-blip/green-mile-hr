import {requireChatGPTUser} from '../chatgpt-auth';
import {loginConfigured} from '../hr-auth';
import {redirect} from 'next/navigation';
import LoginForm from '../login/login-form';
export const dynamic='force-dynamic';
export default async function ForgotPassword(){const user=await requireChatGPTUser('/forgot-password');if(!await loginConfigured(user.userId))redirect('/login');return <LoginForm setup={false} recovery email={user.email}/>}
