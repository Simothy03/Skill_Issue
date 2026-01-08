'use client'

import { useState } from 'react'
import { Dialog, DialogBackdrop, DialogPanel, TransitionChild } from '@headlessui/react'
import {
  Bars3Icon,
  HomeIcon,
  XMarkIcon,
  Cog8ToothIcon,
} from '@heroicons/react/24/outline'
import { Link, useLocation, useNavigate } from 'react-router-dom'

const API_URL = import.meta.env.REACT_APP_API_URL || import.meta.env.VITE_REACT_APP_API_URL;
const API = API_URL ? `${API_URL}` : "http://localhost:5000";

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: HomeIcon },
  { name: 'Settings', href: '/options', icon: Cog8ToothIcon },
]

function classNames(...classes) {
  return classes.filter(Boolean).join(' ')
}

export default function Sidebar({children}) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation() 
  const currentPath = location.pathname 
  const navigate = useNavigate()

  const isCurrent = (href) => currentPath === href

  const handleLogout = async () => {
    try {
      await fetch(`${API}/logout`, {
        method: "GET",
        credentials: "include",
      })
    } catch (err) {
      console.error("Logout failed", err)
    } finally {
      navigate("/")
    }
  }

  return (
    <>
      <div>
        {/* Mobile Sidebar Dialog */}
        <Dialog open={sidebarOpen} onClose={setSidebarOpen} className="relative z-50 lg:hidden">
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

              <div className="relative flex grow flex-col gap-y-5 overflow-y-auto bg-white px-6 pb-2">
                <div className="relative flex h-16 shrink-0 items-center">
                  <img
                    src="/images/Skill_Issue_Logo_Abbr.png"
                    alt="Skill Issue Logo"
                    className="h-8 w-auto"
                  />
                </div>
                <nav className="relative flex flex-1 flex-col">
                  <ul role="list" className="flex flex-1 flex-col gap-y-7">
                    <li>
                      <ul role="list" className="-mx-2 space-y-1">
                        {navigation.map((item) => (
                          <li key={item.name}>
                            <Link
                              to={item.href}
                              onClick={() => setSidebarOpen(false)} // Close on click for mobile
                              className={classNames(
                                isCurrent(item.href)
                                  ? 'bg-gray-50 text-indigo-600'
                                  : 'text-gray-700 hover:bg-gray-50 hover:text-indigo-600',
                                'group flex gap-x-3 rounded-md p-2 text-sm/6 font-semibold',
                              )}
                            >
                              <item.icon
                                aria-hidden="true"
                                className={classNames(
                                  isCurrent(item.href) ? 'text-indigo-600' : 'text-gray-400 group-hover:text-indigo-600',
                                  'size-6 shrink-0',
                                )}
                              />
                              {item.name}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </li>
                    <li className="-mx-6 mt-auto">
                      <button
                        onClick={handleLogout}
                        className="flex w-full items-center gap-x-3 px-6 py-3 text-sm font-semibold text-red-600 hover:bg-red-50"
                      >
                        Logout
                      </button>
                    </li>
                  </ul>
                </nav>
              </div>
            </DialogPanel>
          </div>
        </Dialog>

        {/* Static Sidebar for Desktop */}
        <div className="hidden lg:fixed lg:inset-y-0 lg:z-50 lg:flex lg:w-72 lg:flex-col">
          <div className="flex grow flex-col gap-y-5 overflow-y-auto border-r border-gray-200 bg-white px-6">
            <div className="flex h-16 shrink-0 items-center">
              <img
                src="/images/Skill_Issue_Logo_Abbr.png"
                alt="Skill Issue Logo"
                className="h-8 w-auto"
              />
            </div>
            <nav className="flex flex-1 flex-col">
              <ul role="list" className="flex flex-1 flex-col gap-y-7">
                <li>
                  <ul role="list" className="-mx-2 space-y-1">
                    {navigation.map((item) => (
                      <li key={item.name}>
                        <Link
                          to={item.href}
                          className={classNames(
                            isCurrent(item.href) 
                              ? 'bg-gray-50 text-indigo-600'
                              : 'text-gray-700 hover:bg-gray-50 hover:text-indigo-600',
                            'group flex gap-x-3 rounded-md p-2 text-sm/6 font-semibold',
                          )}
                        >
                          <item.icon
                            aria-hidden="true"
                            className={classNames(
                              isCurrent(item.href) ? 'text-indigo-600' : 'text-gray-400 group-hover:text-indigo-600',
                              'size-6 shrink-0',
                            )}
                          />
                          {item.name}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </li>
                <li className="-mx-6 mt-auto border-t border-gray-200">
                  <button
                    onClick={handleLogout}
                    className="flex w-full items-center gap-x-3 px-6 py-3 text-sm font-semibold text-red-600 hover:bg-red-50"
                  >
                    Logout
                  </button>
                </li>
              </ul>
            </nav>
          </div>
        </div>

        {/* Mobile Header Bar */}
        <div className="sticky top-0 z-40 flex items-center gap-x-6 bg-white px-4 py-4 shadow-sm sm:px-6 lg:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="-m-2.5 p-2.5 text-gray-700 hover:text-gray-900"
          >
            <span className="sr-only">Open sidebar</span>
            <Bars3Icon aria-hidden="true" className="size-6" />
          </button>
          <div className="flex-1 text-sm font-semibold text-gray-900">
            <img
              src="/images/Skill_Issue_Logo_Abbr.png"
              alt="Skill Issue Logo"
              className="h-6 w-auto"
            />
          </div>
        </div>

        <main className="lg:pl-72">
          <div className="px-4 py-10 sm:px-6 lg:px-8">{children}</div>
        </main>
      </div>
    </>
  )
}