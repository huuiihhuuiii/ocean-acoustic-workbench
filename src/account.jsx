import React, { createContext, useContext, useEffect, useState } from "react";
import { LogIn, Users } from "lucide-react";
import { useChatSession } from "./chat-session";
const AccountContext = createContext({
  loading: true,
  available: false,
  authenticated: false,
});
export function AccountProvider({ children }) {
  const { ready } = useChatSession();
  const [account, setAccount] = useState({
    loading: true,
    available: false,
    authenticated: false,
  });
  useEffect(() => {
    if (!ready) return;
    let alive = true;
    fetch("/api/account", { credentials: "same-origin" })
      .then(async (response) => {
        if (!response.ok) throw new Error("账户状态暂不可用。");
        const value = await response.json();
        if (alive)
          setAccount({
            ...value,
            loading: false,
            available: true,
            authenticated: value.authenticated === true,
          });
      })
      .catch((error) => {
        if (alive)
          setAccount({
            loading: false,
            available: false,
            authenticated: false,
            error: error.message,
          });
      });
    return () => {
      alive = false;
    };
  }, [ready]);
  return (
    <AccountContext.Provider value={account}>
      {children}
    </AccountContext.Provider>
  );
}
export const useAccount = () => useContext(AccountContext);
export function AccountBadge({ onOpen }) {
  const account = useAccount();
  if (account.loading)
    return <div className="account-badge checking">正在读取个人空间…</div>;
  if (!account.available) return null;
  return account.authenticated ? (
    <button type="button" className="account-badge" onClick={onOpen}>
      <span className="account-avatar">
        {(account.display_name || "我").slice(0, 1)}
      </span>
      <span>
        {account.display_name || "已登录账户"}
        <small>账户空间 · 跨设备同步</small>
      </span>
      <Users size={13} />
    </button>
  ) : (
    <a
      className="account-badge sign-in"
      href={account.sign_in_url || "/signin-with-chatgpt?return_to=%2F"}
      target="_top"
    >
      <LogIn size={15} />
      <span>
        登录并同步研究<small>会话与密钥仍按个人隔离</small>
      </span>
    </a>
  );
}
