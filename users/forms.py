from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.models import User
from events.models import Event, Group
from users.models import Profile, GroupDelegation, GroupRole
from two_factor.forms import TOTPDeviceForm as BaseTOTPDeviceForm
import base64

class UserRegisterForm(UserCreationForm):
    eula_agreement = forms.BooleanField(
        required=True,
        label="I agree to the End User License Agreement (EULA)",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_eula_agreement'
        }),
        error_messages={
            'required': 'You must agree to the End User License Agreement to create an account.'
        }
    )
    
    class Meta:
        model = User
        fields = ['username', 'email']

class UserProfileForm(forms.ModelForm):
    admin_groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label="Groups"
    )
    clear_profile_picture = forms.BooleanField(required=False, label="Remove Profile Picture")
    can_post_blog = forms.BooleanField(required=False, label="Can post blog posts to Bluesky")

    class Meta:
        model = Profile
        fields = ['display_name', 'profile_picture_base64', 'discord_username', 'telegram_username', 'can_post_blog']
        widgets = {
            'display_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your display name'
            }),
            'discord_username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your Discord username'
            }),
            'telegram_username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your Telegram username'
            }),
            'profile_picture_base64': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['admin_groups'].initial = Group.objects.filter(group_roles__user=self.instance.user)
        if self.instance and self.instance.profile_picture_base64:
            self.initial['profile_picture_base64'] = self.instance.profile_picture_base64
        # Only show can_post_blog to superusers
        if not (self.instance and self.instance.user and self.instance.user.is_superuser):
            self.fields.pop('can_post_blog', None)

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if self.instance and self.instance.user:
            selected_groups = self.cleaned_data.get('admin_groups', Group.objects.none())
            # Add new GroupRoles
            for group in selected_groups:
                GroupRole.objects.get_or_create(user=self.instance.user, group=group)
            # Remove GroupRoles for groups not selected
            GroupRole.objects.filter(user=self.instance.user).exclude(group__in=selected_groups).delete()
        return instance

class UserPublicProfileForm(forms.ModelForm):
    clear_profile_picture = forms.BooleanField(required=False, label="Remove Profile Picture")
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter your email address'
    }))

    class Meta:
        model = Profile
        fields = ['display_name', 'discord_username', 'telegram_username', 'profile_picture_base64']
        widgets = {
            'display_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your display name'
            }),
            'discord_username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your Discord username'
            }),
            'telegram_username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your Telegram username'
            }),
            'profile_picture_base64': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.profile_picture_base64:
            self.initial['profile_picture_base64'] = self.instance.profile_picture_base64
        if self.instance and self.instance.user:
            self.initial['email'] = self.instance.user.email

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            if 'email' in self.cleaned_data:
                instance.user.email = self.cleaned_data['email']
                instance.user.save(update_fields=['email'])
        return instance

class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']

class RenameGroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']

class AssistantAssignmentForm(forms.ModelForm):
    delegated_user = forms.ModelChoiceField(queryset=User.objects.filter(is_superuser=False).exclude(id=None), label="Assign User as Assistant")
    group = forms.ModelChoiceField(queryset=Group.objects.all(), label="For Group")

    class Meta:
        model = GroupDelegation
        fields = ['delegated_user', 'group']

    def __init__(self, *args, **kwargs):
        organizer_profile = kwargs.pop('organizer_profile', None)
        super().__init__(*args, **kwargs)
        if organizer_profile and organizer_profile.user:
            self.fields['group'].queryset = Group.objects.filter(group_roles__user=organizer_profile.user).distinct()
        if organizer_profile and organizer_profile.user:
            self.fields['delegated_user'].queryset = self.fields['delegated_user'].queryset.exclude(id=organizer_profile.user.id)

class UserPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs['class'] = 'form-control'

class GroupRoleForm(forms.ModelForm):
    class Meta:
        model = GroupRole
        fields = ['user', 'custom_label', 'can_post', 'can_manage_leadership'] 

class TOTPDeviceForm(BaseTOTPDeviceForm):
    pass 

class BlueskyBlogPostForm(forms.Form):
    title = forms.CharField(max_length=300, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Title'}))
    content = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Write your blog post here...', 'rows': 6})) 
