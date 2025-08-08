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
  AppstoreOutlined,
  SettingOutlined,
  LinkOutlined,
  FileTextOutlined,
  FolderOutlined
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
      key: '/mcp-connections',
      icon: <LinkOutlined />,
      label: 'MCP Connections',
    },
    {
      key: '/agents',
      icon: <RobotOutlined />,
      label: 'Agents',
    },
    {
      key: '/workspaces',
      icon: <FolderOutlined />,
      label: 'Workspaces',
    },
    {
      key: '/documents',
      icon: <FileTextOutlined />,
      label: 'Documents',
    },
    {
      key: '/chat',
      icon: <MessageOutlined />,
      label: 'Chat',
    },
    {
      key: '/chat-agents',
      icon: <RobotOutlined />,
      label: 'Agent Chat',
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
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: 'Settings',
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
    if (currentPath.startsWith('/mcp-connections')) return '/mcp-connections';
    if (currentPath.startsWith('/agents')) return '/agents';
    if (currentPath.startsWith('/workspaces')) return '/workspaces';
    if (currentPath.startsWith('/documents')) return '/documents';
    if (currentPath === '/chat-agents') return '/chat-agents';
    if (currentPath.startsWith('/chat')) return '/chat';
    if (currentPath.startsWith('/demos')) return '/demos';
    if (currentPath.startsWith('/logs')) return '/logs';
    if (currentPath.startsWith('/settings')) return '/settings';
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