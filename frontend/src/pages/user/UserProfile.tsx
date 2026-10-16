import ProfileSettings from '../../components/ProfileSettings';
import SetManualPassword from '../../components/SetManualPassword';
import { useAuth } from '../../context/AuthContext';

export default function UserProfile() {
  const { user } = useAuth();

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <ProfileSettings />
      {!user?.hasUsablePassword && <SetManualPassword />}
    </div>
  );
}
