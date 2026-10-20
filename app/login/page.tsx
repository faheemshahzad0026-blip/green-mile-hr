import {requireChatGPTUser} from '../chatgpt-auth';
import {getChatGPTUser,loginConfigured} from '../hr-auth';
import {redirect} from 'next/navigation';
import LoginForm from './login-form';
export const dynamic='force-dynamic';
export default async function Login(){const user=await requireChatGPTUser('/login');if(await getChatGPTUser())redirect('/');return <LoginForm setup={!await loginConfigured(user.userId)}/>}
