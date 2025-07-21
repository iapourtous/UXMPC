import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import {
  ApiOutlined,
  RobotOutlined,
  DatabaseOutlined,
  MessageOutlined,
  FileSearchOutlined,
  ToolOutlined,
  ThunderboltOutlined,
  AppstoreOutlined
} from '@ant-design/icons';

const { Header } = Layout;

const AppHeader = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: '/services',
      icon: <ToolOutlined />,
      label: 'Services',
    },
    {
      key: '/llms',
      icon: <DatabaseOutlined />,
      label: 'LLM Profiles',
    },
    {
      key: '/agents',
      icon: <RobotOutlined />,
      label: 'Agents',
    },
    {
      key: '/chat',
      icon: <MessageOutlined />,
      label: 'Chat',
    },
    {
      key: '/meta-chat',
      icon: <ThunderboltOutlined />,
      label: 'Meta Chat',
    },
    {
      key: '/demos',
      icon: <AppstoreOutlined />,
      label: 'Demos',
    },
    {
      key: '/logs',
      icon: <FileSearchOutlined />,
      label: 'Logs',
    }
  ];

  const handleMenuClick = (e) => {
    navigate(e.key);
  };

  // Determine selected key based on current path
  const getSelectedKey = () => {
    const currentPath = location.pathname;
    if (currentPath.startsWith('/services')) return '/services';
    if (currentPath.startsWith('/llms')) return '/llms';
    if (currentPath.startsWith('/agents')) return '/agents';
    if (currentPath.startsWith('/chat')) return '/chat';
    if (currentPath.startsWith('/meta-chat')) return '/meta-chat';
    if (currentPath.startsWith('/logs')) return '/logs';
    return '/agents';
  };

  return (
    <Header style={{ display: 'flex', alignItems: 'center', padding: '0 24px' }}>
      <div style={{ 
        color: 'white', 
        fontSize: '20px', 
        fontWeight: 'bold',
        marginRight: '40px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
      }}>
        <ApiOutlined style={{ fontSize: '24px' }} />
        UXMCP
      </div>
      <Menu
        key={location.pathname}
        theme="dark"
        mode="horizontal"
        selectedKeys={[getSelectedKey()]}
        items={menuItems}
        onClick={handleMenuClick}
        style={{ flex: 1, minWidth: 0 }}
      />
    </Header>
  );
};

export default AppHeader;