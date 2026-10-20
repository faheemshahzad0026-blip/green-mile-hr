import {requireChatGPTUser} from './chatgpt-auth';
import {getChatGPTUser} from './hr-auth';
import {redirect} from 'next/navigation';
import HRApp from './hr-app';
export const dynamic='force-dynamic';
export default async function Home(){await requireChatGPTUser('/');const user=await getChatGPTUser();if(!user)redirect('/login');return <HRApp user={user.displayName}/>}
