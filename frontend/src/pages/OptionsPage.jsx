'use client'

import React, { useState, useEffect, useRef } from 'react';
import { Dialog, DialogBackdrop, DialogPanel, TransitionChild } from '@headlessui/react'
import { Link, useLocation, useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar'

// API Configuration
const API_URL = import.meta.env.REACT_APP_API_URL || import.meta.env.VITE_REACT_APP_API_URL;
const API = API_URL ? `${API_URL}` : "http://localhost:5000"; 


import {
  XMarkIcon,
} from '@heroicons/react/24/outline'

function classNames(...classes) {
  return classes.filter(Boolean).join(' ')
}

export default function OptionsPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  
  // --- START: Data Fetching Logic and Editable State ---
  const [userInfo, setUserInfo] = useState(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // NEW STATE for editable fields
  const [editableName, setEditableName] = useState('');
  const [editableChessUsername, setEditableChessUsername] = useState('');
  
  const navigate = useNavigate();
  const hasFetched = useRef(false);

  const fetchUserStatus = async () => {
    try {
      const response = await fetch(`${API}/api/user/status`, {
        method: 'GET',
        credentials: 'include',
      });

      const data = await response.json();

      if (data.logged_in) {
        setIsLoggedIn(true);
        setUserInfo(data.user_info);
        
        // --- INITIALIZE EDITABLE STATE HERE ---
        setEditableName(data.user_info?.name || '');
        setEditableChessUsername(data.user_info?.chess_com_username || 'Not Linked');
        // --------------------------------------
        
      } else {
        navigate('/login?error=session_expired');
      }

    } catch (err) {
      setError('Failed to fetch user status.');
    } finally {
      setLoading(false);
      hasFetched.current = true;
    }
  };

  useEffect(() => {
    fetchUserStatus();
  }, [navigate]);

  // Handle Loading/Auth States
  if (loading && !hasFetched.current) {
    return <div className="min-h-screen bg-gray-100 flex items-center justify-center"><p>Loading...</p></div>;
  }
  
  if (!isLoggedIn) {
    return <div className="min-h-screen bg-gray-100 flex items-center justify-center"><p>Please <a href="/login" className="text-blue-600">login</a>.</p></div>;
  }

  // Email is read-only, so we can pull it directly from userInfo
  const currentEmail = userInfo?.email || '';
  
  // --- END: Data Fetching Logic and Editable State ---

  return (
    <Sidebar>
    <>
      <div>
        {/* Mobile sidebar dialog remains */}
        <Dialog open={sidebarOpen} onClose={setSidebarOpen} className="relative z-50 xl:hidden">
          <DialogBackdrop
            transition
            className="fixed inset-0 bg-gray-900/80 transition-opacity duration-300 ease-linear data-[closed]:opacity-0"
          />

          <div className="fixed inset-0 flex">
            <DialogPanel
              transition
              className="relative mr-16 flex w-full max-w-xs flex-1 transform transition duration-300 ease-in-out data-[closed]:-translate-x-full"
            >
              <TransitionChild>
                <div className="absolute left-full top-0 flex w-16 justify-center pt-5 duration-300 ease-in-out data-[closed]:opacity-0">
                  <button type="button" onClick={() => setSidebarOpen(false)} className="-m-2.5 p-2.5">
                    <span className="sr-only">Close sidebar</span>
                    <XMarkIcon aria-hidden="true" className="size-6 text-white" />
                  </button>
                </div>
              </TransitionChild>
            </DialogPanel>
          </div>
        </Dialog>

        <div className="xl:pl-72">
          <main>
            <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>
            {error && (
                <div className="mb-4 p-4 bg-red-100 text-red-700 rounded-md">
                    <h3 className="font-bold">Error</h3>
                    <p>{error}</p>
                </div>
            )}

            {/* Settings forms */}
            <div className="divide-y divide-gray-200">
              <div className="grid max-w-7xl grid-cols-1 gap-x-8 gap-y-10 px-4 py-16 sm:px-6 md:grid-cols-3 lg:px-8">
                <div>
                  <h2 className="text-base/7 font-semibold text-gray-900">Personal Information</h2>
                  <p className="mt-1 text-sm/6 text-gray-500">You may change your linked Chess.com account up to once every month.</p>
                </div>

                {/* The main form for editing personal info */}
                <form className="md:col-span-2">
                  <div className="grid grid-cols-1 gap-x-6 gap-y-8 sm:max-w-xl sm:grid-cols-6">

                    {/* 1. Name Field (Now Editable) */}
                    <div className="col-span-full">
                      <label htmlFor="first-name" className="block text-sm/6 font-medium text-gray-900">
                        Name
                      </label>
                      <div className="mt-2">
                        <input
                          id="first-name"
                          name="first-name"
                          type="text"
                          autoComplete="given-name"
                          // Use editable state
                          value={editableName} 
                          // Add onChange handler for controlled component
                          onChange={(e) => setEditableName(e.target.value)} 
                          className="block w-full rounded-md bg-white px-3 py-1.5 text-base text-gray-900 outline outline-1 -outline-offset-1 outline-gray-300 placeholder:text-gray-400 focus:outline focus:outline-2 focus:-outline-offset-2 focus:outline-indigo-600 sm:text-sm/6"
                        />
                      </div>
                    </div>

                    {/* 2. Email Field (Read-Only) */}
                    <div className="col-span-full">
                      <label htmlFor="email" className="block text-sm/6 font-medium text-gray-900">
                        Email Address
                      </label>
                      <div className="mt-2">
                        <input
                          id="email"
                          name="email"
                          type="email"
                          autoComplete="email"
                          readOnly
                          value={currentEmail} 
                          className="block w-full rounded-md bg-gray-100 px-3 py-1.5 text-base text-gray-900 outline outline-1 -outline-offset-1 outline-gray-300 placeholder:text-gray-400 sm:text-sm/6"
                        />
                      </div>
                    </div>

                    {/* 3. Chess.com Username Field (Now Editable) */}
                    <div className="col-span-full">
                      <label htmlFor="username" className="block text-sm/6 font-medium text-gray-900">
                        Chess.com Username
                      </label>
                      <div className="mt-2">
                        <div className="flex items-center rounded-md bg-white pl-3 outline outline-1 -outline-offset-1 outline-gray-300 focus-within:outline focus-within:outline-2 focus-within:-outline-offset-2 focus-within:outline-indigo-600 sm:text-sm/6">
                          <div className="shrink-0 select-none text-base text-gray-500 sm:text-sm/6"></div>
                          <input
                            id="username"
                            name="username"
                            type="text"
                            placeholder="e.g. hikaru"
                            // Use editable state
                            value={editableChessUsername}
                            // Add onChange handler for controlled component
                            onChange={(e) => setEditableChessUsername(e.target.value)}
                            className="block min-w-0 grow bg-transparent py-1.5 pl-1 pr-3 text-base text-gray-900 placeholder:text-gray-400 focus:outline focus:outline-0 sm:text-sm/6"
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-8 flex">
                    <button
                      type="submit"
                      className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
                    >
                      Save
                    </button>
                  </div>
                </form>
              </div>

              <div className="grid max-w-7xl grid-cols-1 gap-x-8 gap-y-10 px-4 py-16 sm:px-6 md:grid-cols-3 lg:px-8">
                <div>
                  <h2 className="text-base/7 font-semibold text-gray-900">Delete account</h2>
                  <p className="mt-1 text-sm/6 text-gray-500">
                    No longer want to use Skill Issue? You can delete your account here. This action is not reversible.
                    All information related to this account will be deleted permanently.
                  </p>
                </div>

                <form className="flex items-start md:col-span-2">
                  <button
                    type="submit"
                    className="rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500"
                  >
                    Yes, delete my account
                  </button>
                </form>
              </div>
            </div>
          </main>
        </div>
      </div>
    </>
    </Sidebar>
  )
}